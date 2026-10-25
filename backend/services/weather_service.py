"""
AgroNex AI — Module 3: Weather Intelligence and Farm Safety Service
Integrates Open-Meteo Numerical Weather Forecasts with plant pathology micro-climate
risk intelligence and agricultural spray-condition advisory rules.
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import httpx
from config.weather_thresholds import (
    SPRAY_RAIN_PROB_THRESHOLD,
    SPRAY_PRECIP_THRESHOLD_MM,
    SPRAY_WIND_SPEED_THRESHOLD_KMH,
)
from services.weather_alert_service import WeatherAlertService

logger = logging.getLogger(__name__)


def validate_coordinates(lat: Any, lon: Any) -> Tuple[float, float]:
    """
    Validates latitude and longitude coordinates.
    Latitude must be between -90 and 90 degrees.
    Longitude must be between -180 and 180 degrees.
    Returns rounded (lat, lon) to 4 decimal places.
    """
    if lat is None or lon is None:
        raise ValueError("Latitude and Longitude parameters are required.")
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid coordinate format: lat={lat}, lon={lon}")

    if not (-90.0 <= lat_f <= 90.0):
        raise ValueError(f"Latitude must be between -90 and 90 degrees. Received: {lat_f}")
    if not (-180.0 <= lon_f <= 180.0):
        raise ValueError(f"Longitude must be between -180 and 180 degrees. Received: {lon_f}")

    return round(lat_f, 4), round(lon_f, 4)


class WeatherService:
    """
    Reusable, decoupled Weather Intelligence Service.
    - Connects to Open-Meteo Numerical Forecast API
    - Implements in-memory caching with TTL (Time-To-Live)
    - Validates locations and prevents misleading silent defaults
    - Evaluates agricultural spray window caution triggers
    - Analyzes foliar micro-climate pathology favorability without declaring diagnosis
    """

    DEFAULT_CACHE_TTL_SECONDS = 900  # 15 minutes
    DEFAULT_TIMEOUT_SECONDS = 8.0     # 8 seconds connection/read timeout

    def __init__(self, cache_ttl: int = DEFAULT_CACHE_TTL_SECONDS, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.alert_service = WeatherAlertService()
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        # Cache entries format: {cache_key: (timestamp, data_dict)}
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def get_weather(
        self,
        lat: float,
        lon: float,
        crop: Optional[str] = None,
        condition: Optional[str] = None,
        location_source: Optional[str] = None,
        location_name: Optional[str] = None,
        bypass_cache: bool = False,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Retrieves real-time Open-Meteo numerical weather forecasts.
        Includes 24-hour hourly resolution, 7-day daily outlook, units, retrieval timestamps,
        and embedded spray-condition advisory evaluation.
        """
        # 1. Validate coordinates
        try:
            valid_lat, valid_lon = validate_coordinates(lat, lon)
        except ValueError as ve:
            return {
                "success": False,
                "data_available": False,
                "error": f"Invalid coordinates: {str(ve)}",
                "location": {
                    "latitude": lat,
                    "longitude": lon,
                    "location_name": location_name or f"Invalid ({lat}, {lon})",
                    "location_source": "invalid",
                    "is_default_location": False,
                },
                "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                "is_cached": False,
            }

        cache_key = f"{round(valid_lat, 2)}_{round(valid_lon, 2)}"
        now_ts = time.time()

        # 2. Check fresh cache
        if not bypass_cache and cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            cache_age = now_ts - cached_time
            if cache_age < self.cache_ttl:
                # Return fresh cached response
                fresh_copy = dict(cached_data)
                fresh_copy["is_cached"] = True
                fresh_copy["cache_status"] = "fresh"
                fresh_copy["cache_age_seconds"] = round(cache_age, 1)
                return fresh_copy

        # Compute location metadata
        is_default = (valid_lat == 11.0168 and valid_lon == 76.9558 and not location_name)
        loc_src = location_source or ("fallback_preset" if is_default else "user_coordinates")
        loc_label = location_name or ("Coimbatore (Fallback Preset)" if is_default else f"Coordinates ({valid_lat}, {valid_lon})")

        # 3. Query Open-Meteo API
        base_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": valid_lat,
            "longitude": valid_lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_gusts_10m",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,weather_code",
            "timezone": "auto",
            "forecast_days": 7
        }

        try:
            data = self._fetch_open_meteo(params)

            current = data.get("current", {})
            hourly = data.get("hourly", {})
            daily = data.get("daily", {})
            tz_str = data.get("timezone", "UTC")

            # Weather code descriptive mapping
            code = current.get("weather_code", 0)
            condition_en, condition_ta = self._map_weather_code(code)

            # Format 7-day regional forecast
            forecast = []
            if "time" in daily:
                for i in range(len(daily["time"])):
                    forecast.append({
                        "date": daily["time"][i],
                        "temperature_max": daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                        "temperature_min": daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                        "precipitation_probability_mean": daily.get("precipitation_probability_max", [0])[i] if i < len(daily.get("precipitation_probability_max", [])) else 0,
                        "precipitation_sum": daily.get("precipitation_sum", [0.0])[i] if i < len(daily.get("precipitation_sum", [])) else 0.0,
                    })

            # Format 24-hour forecast starting from current hour
            hourly_forecast = []
            if "time" in hourly:
                current_time_str = current.get("time", "")[:13]
                start_idx = 0
                for i, t in enumerate(hourly["time"]):
                    if t.startswith(current_time_str) or t > current_time_str:
                        start_idx = i
                        break

                end_idx = min(start_idx + 24, len(hourly["time"]))
                for i in range(start_idx, end_idx):
                    hourly_forecast.append({
                        "time": hourly["time"][i],
                        "temperature": hourly["temperature_2m"][i] if "temperature_2m" in hourly and i < len(hourly["temperature_2m"]) else None,
                        "relative_humidity": hourly["relative_humidity_2m"][i] if "relative_humidity_2m" in hourly and i < len(hourly["relative_humidity_2m"]) else None,
                        "precipitation_probability": hourly["precipitation_probability"][i] if "precipitation_probability" in hourly and i < len(hourly["precipitation_probability"]) else 0,
                        "precipitation": hourly["precipitation"][i] if "precipitation" in hourly and i < len(hourly["precipitation"]) else 0.0,
                        "wind_speed": hourly["wind_speed_10m"][i] if "wind_speed_10m" in hourly and i < len(hourly["wind_speed_10m"]) else None,
                        "weather_code": hourly["weather_code"][i] if "weather_code" in hourly and i < len(hourly["weather_code"]) else 0,
                    })

            # Weather alerts
            alerts = self.alert_service.generate_alerts(data, crop, condition)

            # Timestamps
            retrieval_iso = datetime.now(timezone.utc).isoformat()
            current_time = current.get("time", retrieval_iso)

            validity_start = hourly_forecast[0]["time"] if hourly_forecast else current_time
            validity_end = hourly_forecast[-1]["time"] if hourly_forecast else current_time

            result = {
                "success": True,
                "data_available": True,
                "data_source": "Open-Meteo Numerical Weather Model Forecast",
                "is_field_measurement": False,
                "is_live_radar": False,
                "data_accuracy_notice": "Forecast values are derived from numerical weather prediction models and are not measurements from an on-field physical sensor station.",
                "location": {
                    "latitude": valid_lat,
                    "longitude": valid_lon,
                    "location_name": loc_label,
                    "location_source": loc_src,
                    "is_default_location": is_default,
                },
                "timezone": tz_str,
                "last_updated": current_time,
                "forecast_retrieval_time": retrieval_iso,
                "forecast_validity_start": validity_start,
                "forecast_validity_end": validity_end,
                "forecast_horizon": "7-day daily forecast, 24-hour hourly resolution",
                "units": {
                    "temperature": "°C",
                    "relative_humidity": "%",
                    "precipitation_probability": "%",
                    "precipitation": "mm",
                    "wind_speed": "km/h"
                },
                "condition_en": condition_en,
                "condition_ta": condition_ta,
                "current": {
                    "temperature": current.get("temperature_2m"),
                    "humidity": current.get("relative_humidity_2m"),
                    "apparent_temperature": current.get("apparent_temperature"),
                    "wind_speed": current.get("wind_speed_10m"),
                    "wind_gusts": current.get("wind_gusts_10m"),
                    "precipitation": current.get("precipitation", 0.0),
                    "weather_code": code
                },
                "hourly": hourly_forecast,
                "forecast": forecast,
                "alerts": alerts,
                "is_cached": False,
                "cache_status": "fresh",
                "cache_age_seconds": 0.0,
            }

            # Evaluate spray condition advisory
            result["spray_advisory"] = self.evaluate_spray_advisory(
                weather_data=result,
                language=language
            )

            # Store in cache
            self._cache[cache_key] = (now_ts, result)
            self._cache["_last"] = (now_ts, result)

            return result

        except (httpx.HTTPError, TimeoutError, Exception) as e:
            logger.warning(f"Open-Meteo API query error for ({valid_lat}, {valid_lon}): {e}")

            # If stale cache exists, serve it clearly marked
            if cache_key in self._cache or "_last" in self._cache:
                target_cache = self._cache.get(cache_key) or self._cache["_last"]
                cached_time, cached_data = target_cache
                cache_age = now_ts - cached_time
                stale_copy = dict(cached_data)
                stale_copy["is_cached"] = True
                stale_copy["cache_status"] = "stale"
                stale_copy["cache_age_seconds"] = round(cache_age, 1)
                stale_copy["warning"] = f"Serving cached forecast data. Open-Meteo API error: {str(e)}"
                return stale_copy

            # NEVER invent fake data when Open-Meteo is unavailable and no cache exists!
            return {
                "success": False,
                "data_available": False,
                "error": f"Open-Meteo forecast service temporarily unavailable: {str(e)}",
                "location": {
                    "latitude": valid_lat,
                    "longitude": valid_lon,
                    "location_name": loc_label,
                    "location_source": loc_src,
                    "is_default_location": is_default,
                },
                "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                "data_source": "Open-Meteo Numerical Weather Model Forecast (Offline)",
                "is_field_measurement": False,
                "is_live_radar": False,
                "is_cached": False,
            }

    def evaluate_spray_advisory(
        self,
        weather_data: Dict[str, Any],
        rain_prob_threshold: float = SPRAY_RAIN_PROB_THRESHOLD,
        precip_threshold_mm: float = SPRAY_PRECIP_THRESHOLD_MM,
        wind_speed_threshold_kmh: float = SPRAY_WIND_SPEED_THRESHOLD_KMH,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Section 5 Spray-Condition Advisory Engine.
        Evaluates configurable caution warning triggers across the upcoming 24-hour forecast window.
        Returns triggered_rules, actual_forecast_values, threshold_values, forecast_time,
        explanation, advisory_level, missing_information, and explicit agronomic limitations.
        """
        lang = "ta" if "ta" in (language or "").lower() else "en"
        current = weather_data.get("current", {})
        hourly = weather_data.get("hourly", [])

        # Check for missing variables
        missing_info = []
        if not current.get("temperature") and not any(h.get("temperature") is not None for h in hourly):
            missing_info.append("temperature")
        if not current.get("humidity") and not any(h.get("relative_humidity") is not None for h in hourly):
            missing_info.append("relative_humidity")
        if not hourly or not any(h.get("precipitation_probability") is not None for h in hourly):
            missing_info.append("precipitation_probability")
        if not current.get("wind_speed") and not any(h.get("wind_speed") is not None for h in hourly):
            missing_info.append("wind_speed")

        # Extract values across 24-hour window
        eval_window = hourly[:24] if hourly else []

        curr_precip = float(current.get("precipitation") or 0.0)
        curr_wind = float(current.get("wind_speed") or 0.0)
        curr_temp = current.get("temperature")
        curr_humidity = current.get("humidity")

        max_precip_prob = 0
        max_precip_mm = curr_precip
        max_wind_kmh = curr_wind

        if eval_window:
            probs = [h.get("precipitation_probability", 0) for h in eval_window if h.get("precipitation_probability") is not None]
            if probs:
                max_precip_prob = max(probs)

            precips = [h.get("precipitation", 0.0) for h in eval_window if h.get("precipitation") is not None]
            if precips:
                max_precip_mm = max(max_precip_mm, max(precips))

            winds = [h.get("wind_speed", 0.0) for h in eval_window if h.get("wind_speed") is not None]
            if winds:
                max_wind_kmh = max(max_wind_kmh, max(winds))

        # Check caution triggers
        triggered_rules: List[str] = []
        is_rain_prob_triggered = max_precip_prob > rain_prob_threshold
        is_precip_amount_triggered = max_precip_mm > precip_threshold_mm
        is_wind_triggered = (max_wind_kmh > wind_speed_threshold_kmh) or (curr_wind > wind_speed_threshold_kmh)

        if is_rain_prob_triggered:
            triggered_rules.append("RAIN_PROBABILITY_EXCEEDED")
        if is_precip_amount_triggered:
            triggered_rules.append("PRECIPITATION_AMOUNT_EXCEEDED")
        if is_wind_triggered:
            triggered_rules.append("WIND_SPEED_EXCEEDED")

        # Advisory level and explanations
        if is_rain_prob_triggered or is_precip_amount_triggered:
            advisory_level = "HIGH_RISK"
            if lang == "ta":
                explanation = (
                    f"மழை வாய்ப்பு {max_precip_prob}% (எச்சரிக்கை வரம்பு: >{rain_prob_threshold}%) அல்லது மழை அளவு {max_precip_mm:.1f} மி.மீ (வரம்பு: >{precip_threshold_mm} மி.மீ) எட்டக்கூடும். "
                    "மழை பெய்தால் தெளிக்கப்பட்ட மருந்து கழுவிச் செல்லப்படலாம் (Rain may wash off the applied product). "
                    "மருந்து பாட்டிலின் லேபிளைப் படித்து உள்ளூர் வேளாண் ஆலோசனையை பின்பற்றவும்."
                )
            else:
                explanation = (
                    f"Precipitation probability reaches {max_precip_prob}% (threshold: >{rain_prob_threshold}%) or forecast precipitation is {max_precip_mm:.1f} mm (threshold: >{precip_threshold_mm} mm). "
                    "Rain may wash off the applied product. High risk of chemical runoff and wasted treatment. "
                    "Review the product label and local agricultural advice."
                )
        elif is_wind_triggered:
            advisory_level = "CAUTION"
            if lang == "ta":
                explanation = (
                    f"காற்றின் வேகம் {max_wind_kmh:.1f} கி.மீ/மணி எச்சரிக்கை வரம்பை (>{wind_speed_threshold_kmh} கி.மீ/மணி) தாண்டக்கூடும். "
                    "காற்றின் வேகம் அதிகமாக இருந்தால் மருந்து காற்றில் அடித்துச் செல்லப்பட்டு விரயமாகலாம் (Wind may increase spray drift). "
                    "மருந்து பாட்டிலின் லேபிளைப் படித்து உள்ளூர் வேளாண் ஆலோசனையை பின்பற்றவும்."
                )
            else:
                explanation = (
                    f"Wind speed reaches {max_wind_kmh:.1f} km/h, exceeding the caution threshold (>{wind_speed_threshold_kmh} km/h). "
                    "Wind may increase spray drift to non-target crops and nearby water bodies. "
                    "Review the product label and local agricultural advice."
                )
        else:
            advisory_level = "FAVORABLE_WINDOW"
            if lang == "ta":
                explanation = (
                    "அடுத்த 24 மணி நேர முன்னறிவிப்பில் காற்றின் வேகம் மற்றும் மழை வாய்ப்பு பொதுவான எச்சரிக்கை வரம்புகளுக்குள் உள்ளன. "
                    "இருப்பினும் தெளிப்பதற்கு முன் பூச்சிக்கொல்லி பாட்டிலின் லேபிளைப் படித்து உள்ளூர் வேளாண் ஆலோசனையை பின்பற்றவும்."
                )
            else:
                explanation = (
                    "Forecasted conditions indicate moderate wind and minimal precipitation probability over the next 24-hour window. "
                    "Review the product label and local agricultural advice."
                )

        # Time range
        forecast_time_str = "Next 24 Hours"
        if eval_window:
            forecast_time_str = f"{eval_window[0].get('time', '')} to {eval_window[-1].get('time', '')}"

        # Limitations notice
        limitations = (
            "முக்கிய வரம்பு: இந்த வானிலை வரம்புகள் பொதுவான எச்சரிக்கை வழிகாட்டலே தவிர, தெளிப்பு பாதுகாப்பானது என்பதற்கான முழு உத்தரவாதம் அல்ல. "
            "பூச்சிக்கொல்லி லேபிள் வழிகாட்டுதல்கள், பயிர் நிலை, தேனீக்கள்/மகரந்த சேர்க்கை நேரம் மற்றும் உள்ளூர் KVK வழிகாட்டுதல்களையே முதன்மையாகப் பின்பற்றவும்."
            if lang == "ta" else
            "Critical Notice: Configured caution thresholds are screening triggers and not universal agronomic safety standards. "
            "Do not assume spraying is completely safe solely because configured weather thresholds are not exceeded. "
            "Always strictly verify specific pesticide product label restrictions, crop growth stage, mandatory buffer zones, pollinator foraging periods, and local Krishi Vigyan Kendra (KVK) guidance."
        )

        return {
            "advisory_level": advisory_level,
            "triggered_rules": triggered_rules,
            "actual_forecast_values": {
                "max_precipitation_probability": max_precip_prob,
                "max_precipitation_mm": round(max_precip_mm, 2),
                "max_wind_speed_kmh": round(max_wind_kmh, 1),
                "current_wind_speed_kmh": round(curr_wind, 1),
                "current_precipitation_mm": round(curr_precip, 2),
                "current_temperature_c": curr_temp,
                "current_humidity_pct": curr_humidity,
            },
            "threshold_values": {
                "precipitation_probability_threshold": rain_prob_threshold,
                "precipitation_amount_threshold_mm": precip_threshold_mm,
                "wind_speed_threshold_kmh": wind_speed_threshold_kmh,
            },
            "forecast_time": forecast_time_str,
            "explanation": explanation,
            "missing_information": missing_info,
            "limitations": limitations,
            "units": {
                "precipitation_probability": "%",
                "precipitation": "mm",
                "wind_speed": "km/h",
                "temperature": "°C"
            }
        }

    def get_environmental_risk(
        self,
        weather_data: Dict[str, Any],
        crop: Optional[str] = None,
        condition: Optional[str] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Module 2 / Section 6 Integration:
        Synthesizes meteorological forecast with plant pathology principles.
        Explains environmental favorability without asserting diagnosis or disease causation.
        """
        lang = "ta" if "ta" in (language or "").lower() else "en"
        curr = weather_data.get("current", {})
        temp = curr.get("temperature", 28.0)
        humidity = curr.get("humidity", 65.0)
        wind = curr.get("wind_speed", 10.0)
        precip = curr.get("precipitation", 0.0)

        rain_prob = 0
        hourly = weather_data.get("hourly", [])
        if hourly:
            rain_prob = max([h.get("precipitation_probability", 0) or 0 for h in hourly[:24]] or [0])

        risk_level = "Low"
        factors_en = []
        factors_ta = []

        if humidity and humidity >= 80:
            risk_level = "Moderate" if risk_level == "Low" else "High"
            factors_en.append(f"High relative humidity ({humidity}%) creates extended foliar moisture conducive to fungal germination.")
            factors_ta.append(f"அதிக காற்றின் ஈரப்பதம் ({humidity}%) பூஞ்சை வித்திகள் முளைத்து பரவுவதற்கு உகந்த ஈரப்பதத்தை அளிக்கிறது.")

        if rain_prob >= 50 or (precip and precip > 1.0):
            risk_level = "High"
            factors_en.append(f"Anticipated rainfall ({rain_prob}% probability) can cause rain splash dispersal and wash off protective treatments.")
            factors_ta.append(f"மழை வாய்ப்பு ({rain_prob}%) மழைத்துளிகள் மூலம் பூஞ்சை சிதறி பரவவும், தெளிக்கப்பட்ட மருந்துகளைக் கழுவிச் செல்லவும் கூடும்.")

        if wind and wind > 20:
            factors_en.append(f"Elevated wind speed ({wind} km/h) creates spray drift hazard and can transport airborne spores.")
            factors_ta.append(f"காற்றின் வேகம் ({wind} கி.மீ/மணி) காற்றில் பூஞ்சை வித்திகளைப் பரப்பலாம் மற்றும் மருந்து தெளிக்கும் போது விரயத்தை ஏற்படுத்தும்.")

        if not factors_en:
            factors_en.append(f"Current weather conditions (Temp {temp}°C, Humidity {humidity}%) represent typical seasonal ranges with baseline foliar risk.")
            factors_ta.append(f"தற்போதைய வானிலை (வெப்பநிலை {temp}°C, ஈரப்பதம் {humidity}%) இயல்பான நிலையில் உள்ளது.")

        return {
            "crop": crop or "General Crop",
            "condition_evaluated": condition or "General Foliage",
            "risk_level": risk_level,
            "relative_humidity_pct": humidity,
            "rain_probability_pct": rain_prob,
            "wind_speed_kmh": wind,
            "environmental_factors": factors_ta if lang == "ta" else factors_en,
            "scientific_disclaimer": (
                "குறிப்பு: இந்த வானிலை பகுப்பாய்வு நுண்ணுயிரிகள் வளர்வதற்கான சுற்றுச்சூழல் சாதகத்தை மட்டுமே விளக்குகிறது. வானிலை மட்டுமே பயிரில் நோய் இருப்பதை நிரூபிக்காது."
                if lang == "ta" else
                "Notice: Meteorological risk intelligence explains micro-climate favorability for pathogens and farm operations. Weather trends alone do not prove or confirm plant infection."
            )
        }

    def _fetch_open_meteo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes HTTP request to Open-Meteo API using httpx with configured timeouts.
        """
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                headers={'User-Agent': 'AgroNex-AI/2.0 (Open-Source Farm Assistant; contact: support@agronex.ai)'}
            )
            resp.raise_for_status()
            return resp.json()

    def _map_weather_code(self, code: int) -> Tuple[str, str]:
        """Maps WMO Weather Interpretation Codes to bilingual descriptors."""
        if code == 0:
            return "Clear sky", "தெளிவான வானம்"
        elif code in [1, 2, 3]:
            return "Partly Cloudy", "பகுதி மேகமூட்டம்"
        elif code in [45, 48]:
            return "Foggy", "மூடுபனி"
        elif code in [51, 53, 55, 56, 57]:
            return "Drizzle", "தூறல் மழை"
        elif code in [61, 63, 65, 66, 67, 80, 81, 82]:
            return "Rain", "மழை"
        elif code in [71, 73, 75, 77, 85, 86]:
            return "Snow / Flurries", "பனிப்பொழிவு"
        elif code in [95, 96, 99]:
            return "Thunderstorm", "இடியுடன் கூடிய மழை"
        return "Overcast", "மேகமூட்டம்"
