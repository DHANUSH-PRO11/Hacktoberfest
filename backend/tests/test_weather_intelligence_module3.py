"""
AgroNex AI — Module 3: Weather Intelligence and Farm Safety Test Suite

Tests:
1. Location Handling & Coordinate Validation:
   - Valid coordinates (-90 to 90 lat, -180 to 180 lon).
   - Invalid coordinates (out-of-bounds lat/lon, non-numeric) returning validation error.
   - Missing coordinates returning HTTP 422.
   - Location source identification and avoidance of misleading silent defaults.
2. Open-Meteo Forecast Integration:
   - 24-hour hourly forecast and 7-day outlook.
   - Explicit units (°C, %, km/h, mm) and retrieval timestamps.
   - Grounded data source labeling (numerical model forecast, not live radar or field sensor).
   - Missing fields handled gracefully without crashes.
3. Weather Service Architecture & Caching:
   - In-memory cache with TTL expiration.
   - Handling API timeouts and connection failures without inventing fake data.
   - Stale cache serving with explicit notice on connection failure.
4. Spray-Condition Advisory Engine:
   - Rain probability threshold (> 60%).
   - Precipitation amount threshold (> 2.0 mm).
   - Wind speed threshold (> 25.0 km/h).
   - Favorable conditions with mandatory limitations notice (never claims spraying is universally safe).
   - Correct units and bilingual explanations.
5. Crop Pathology Environmental Favorability Context:
   - Relative humidity and rain risk factor generation with scientific disclaimer.
6. API Endpoints:
   - GET /api/weather/forecast
   - GET /api/weather/spray-advisory
   - GET /api/weather/risk
   - GET /api/weather/status
"""

import sys
import time
import json
import httpx
import urllib.error
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from services.weather_service import WeatherService, validate_coordinates

client = TestClient(app)


def get_mock_open_meteo_payload():
    """Generates standard Open-Meteo JSON payload dict for unit testing."""
    return {
        "timezone": "Asia/Kolkata",
        "current": {
            "time": "2026-10-25T17:00",
            "temperature_2m": 28.4,
            "relative_humidity_2m": 68.0,
            "apparent_temperature": 30.1,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 12.5,
            "wind_gusts_10m": 18.0
        },
        "hourly": {
            "time": [f"2026-10-25T{h:02d}:00" for h in range(17, 24)] + [f"2026-10-26T{h:02d}:00" for h in range(17)],
            "temperature_2m": [28.0] * 24,
            "relative_humidity_2m": [70.0] * 24,
            "precipitation_probability": [15] * 24,
            "precipitation": [0.0] * 24,
            "weather_code": [1] * 24,
            "wind_speed_10m": [12.0] * 24,
            "wind_gusts_10m": [16.0] * 24
        },
        "daily": {
            "time": [f"2026-10-{d:02d}" for d in range(25, 32)],
            "temperature_2m_max": [31.5] * 7,
            "temperature_2m_min": [23.0] * 7,
            "precipitation_probability_max": [25] * 7,
            "precipitation_sum": [0.2] * 7,
            "weather_code": [1] * 7
        }
    }


def create_mock_open_meteo_response():
    """Generates standard Open-Meteo JSON payload mock response for unit testing."""
    payload = get_mock_open_meteo_payload()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


class TestLocationHandlingAndValidation:
    """Requirement 2: Location Handling & Validation."""

    def test_valid_coordinates(self):
        lat, lon = validate_coordinates(11.0168, 76.9558)
        assert lat == 11.0168
        assert lon == 76.9558

    def test_coordinate_boundaries_edge_cases(self):
        # Extreme valid boundaries
        lat, lon = validate_coordinates(90.0, 180.0)
        assert lat == 90.0
        assert lon == 180.0

        lat, lon = validate_coordinates(-90.0, -180.0)
        assert lat == -90.0
        assert lon == -180.0

    def test_invalid_latitude_raises_value_error(self):
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            validate_coordinates(91.5, 76.9558)

        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            validate_coordinates(-95.0, 76.9558)

    def test_invalid_longitude_raises_value_error(self):
        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            validate_coordinates(11.0168, 185.0)

        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            validate_coordinates(11.0168, -190.0)

    def test_non_numeric_coordinates_raise_value_error(self):
        with pytest.raises(ValueError, match="Invalid coordinate format"):
            validate_coordinates("invalid", "coordinates")

    def test_api_rejects_invalid_coordinates_with_422(self):
        response = client.get("/api/weather/forecast?lat=95.0&lon=76.9558")
        assert response.status_code == 422
        assert "Latitude must be between -90 and 90" in response.json()["detail"]

    def test_api_rejects_missing_coordinates_with_422(self):
        response = client.get("/api/weather/forecast")
        assert response.status_code == 422

    def test_location_source_labeling_prevents_misleading_defaults(self):
        ws = WeatherService()
        # Query with fallback coordinates
        data = ws.get_weather(11.0168, 76.9558)
        assert "location" in data
        assert data["location"]["is_default_location"] is True
        assert "Coimbatore" in data["location"]["location_name"]

        # Query with custom coordinates
        data_custom = ws.get_weather(13.0827, 80.2707, location_source="manual_selection", location_name="Chennai")
        assert data_custom["location"]["is_default_location"] is False
        assert data_custom["location"]["location_source"] == "manual_selection"
        assert data_custom["location"]["location_name"] == "Chennai"


class TestOpenMeteoForecastIntegration:
    """Requirement 3: Forecast Integration & Labeling."""

    def test_forecast_payload_structure_and_units(self):
        ws = WeatherService()
        with patch.object(ws, "_fetch_open_meteo", return_value=get_mock_open_meteo_payload()):
            data = ws.get_weather(11.0168, 76.9558)
            assert data["success"] is True
            assert data["data_available"] is True
            assert data["data_source"] == "Open-Meteo Numerical Weather Model Forecast"
            assert data["is_field_measurement"] is False
            assert data["is_live_radar"] is False

            # Units check
            assert data["units"]["temperature"] == "°C"
            assert data["units"]["relative_humidity"] == "%"
            assert data["units"]["precipitation_probability"] == "%"
            assert data["units"]["precipitation"] == "mm"
            assert data["units"]["wind_speed"] == "km/h"

            # 24-hour and 7-day horizon checks
            assert len(data["hourly"]) <= 24
            assert len(data["forecast"]) <= 7
            assert "forecast_validity_start" in data
            assert "forecast_validity_end" in data

    def test_live_open_meteo_network_query_when_available(self):
        """Completion Criteria 9: Verify real Open-Meteo request when network access is available."""
        ws = WeatherService(timeout=5.0)
        data = ws.get_weather(11.0168, 76.9558, bypass_cache=True)
        if not data["success"]:
            pytest.skip(f"Live network connection to Open-Meteo currently unavailable: {data.get('error')}")
        assert data["data_available"] is True
        assert "current" in data
        assert data["current"]["temperature"] is not None

    def test_missing_forecast_fields_handled_gracefully(self):
        """When an upstream forecast object is missing optional keys, it shouldn't crash."""
        ws = WeatherService()
        sparse_data = {
            "current": {"time": "2026-10-25T16:00:00"},
            "hourly": [],
        }
        advisory = ws.evaluate_spray_advisory(sparse_data)
        assert advisory["advisory_level"] == "FAVORABLE_WINDOW"
        assert len(advisory["missing_information"]) > 0
        assert "temperature" in advisory["missing_information"]


class TestWeatherServiceArchitectureAndCaching:
    """Requirement 4: Service Architecture, Timeouts, and Caching."""

    def test_in_memory_cache_ttl(self):
        ws = WeatherService(cache_ttl=2)  # 2 seconds TTL

        with patch.object(ws, "_fetch_open_meteo", return_value=get_mock_open_meteo_payload()):
            res1 = ws.get_weather(11.0168, 76.9558)
            assert res1["is_cached"] is False

            # Second call immediately should hit fresh cache without calling API
            res2 = ws.get_weather(11.0168, 76.9558)
            assert res2["is_cached"] is True
            assert res2["cache_status"] == "fresh"

        # Wait for TTL to expire
        time.sleep(2.1)
        with patch.object(ws, "_fetch_open_meteo", return_value=get_mock_open_meteo_payload()):
            res3 = ws.get_weather(11.0168, 76.9558)
            # Should be fresh fetch (not cached)
            assert res3["is_cached"] is False
            assert res3["cache_status"] == "fresh"

    def test_api_failure_without_cache_never_invents_fake_measurements(self):
        """When Open-Meteo fails and no cache exists, the service MUST NOT fabricate data."""
        ws = WeatherService()
        ws._cache.clear()

        # Mock httpx failure with connection timeout
        with patch.object(ws, "_fetch_open_meteo", side_effect=httpx.ConnectTimeout("Connection timed out")):
            result = ws.get_weather(25.0, 85.0)

            assert result["success"] is False
            assert result["data_available"] is False
            assert "error" in result
            # Must NOT contain fake measurements
            assert "current" not in result

    def test_api_failure_serves_stale_cache_with_explicit_notice(self):
        ws = WeatherService(cache_ttl=1)
        # Prepopulate cache with mock response
        with patch.object(ws, "_fetch_open_meteo", return_value=get_mock_open_meteo_payload()):
            ws.get_weather(11.0168, 76.9558)

        time.sleep(1.1)

        # Simulate network down
        with patch.object(ws, "_fetch_open_meteo", side_effect=httpx.ConnectError("Network unreachable")):
            result = ws.get_weather(11.0168, 76.9558)
            assert result["success"] is True
            assert result["is_cached"] is True
            assert result["cache_status"] == "stale"
            assert "warning" in result
            assert "Serving cached" in result["warning"]


class TestSprayConditionAdvisoryEngine:
    """Requirement 5: Spray-Condition Advisory Engine."""

    def test_rain_probability_threshold_triggers_high_risk(self):
        ws = WeatherService()
        mock_weather = {
            "current": {"wind_speed": 10.0, "precipitation": 0.0},
            "hourly": [
                {"time": f"2026-10-25T{h:02d}:00", "precipitation_probability": 75 if h == 4 else 20, "precipitation": 0.0, "wind_speed": 10.0}
                for h in range(24)
            ]
        }
        advisory = ws.evaluate_spray_advisory(mock_weather, rain_prob_threshold=60, precip_threshold_mm=2.0, wind_speed_threshold_kmh=25.0)

        assert advisory["advisory_level"] == "HIGH_RISK"
        assert "RAIN_PROBABILITY_EXCEEDED" in advisory["triggered_rules"]
        assert advisory["actual_forecast_values"]["max_precipitation_probability"] == 75
        assert "Rain may wash off" in advisory["explanation"]
        assert "Review the product label" in advisory["explanation"]

    def test_precipitation_amount_threshold_triggers_high_risk(self):
        ws = WeatherService()
        mock_weather = {
            "current": {"wind_speed": 8.0, "precipitation": 0.0},
            "hourly": [
                {"time": f"2026-10-25T{h:02d}:00", "precipitation_probability": 40, "precipitation": 3.5 if h == 2 else 0.0, "wind_speed": 8.0}
                for h in range(24)
            ]
        }
        advisory = ws.evaluate_spray_advisory(mock_weather, rain_prob_threshold=60, precip_threshold_mm=2.0, wind_speed_threshold_kmh=25.0)

        assert advisory["advisory_level"] == "HIGH_RISK"
        assert "PRECIPITATION_AMOUNT_EXCEEDED" in advisory["triggered_rules"]
        assert advisory["actual_forecast_values"]["max_precipitation_mm"] == 3.5
        assert "Rain may wash off" in advisory["explanation"]

    def test_wind_speed_threshold_triggers_caution(self):
        ws = WeatherService()
        mock_weather = {
            "current": {"wind_speed": 28.5, "precipitation": 0.0},
            "hourly": [
                {"time": f"2026-10-25T{h:02d}:00", "precipitation_probability": 10, "precipitation": 0.0, "wind_speed": 28.5 if h == 1 else 12.0}
                for h in range(24)
            ]
        }
        advisory = ws.evaluate_spray_advisory(mock_weather, rain_prob_threshold=60, precip_threshold_mm=2.0, wind_speed_threshold_kmh=25.0)

        assert advisory["advisory_level"] == "CAUTION"
        assert "WIND_SPEED_EXCEEDED" in advisory["triggered_rules"]
        assert advisory["actual_forecast_values"]["max_wind_speed_kmh"] == 28.5
        assert "Wind may increase spray drift" in advisory["explanation"]

    def test_favorable_conditions_never_claims_universal_safety(self):
        """Even when all thresholds pass, the advisory MUST state limitations and product label requirements."""
        ws = WeatherService()
        mock_weather = {
            "current": {"wind_speed": 10.0, "precipitation": 0.0, "temperature": 27.0, "humidity": 65.0},
            "hourly": [
                {"time": f"2026-10-25T{h:02d}:00", "precipitation_probability": 15, "precipitation": 0.0, "wind_speed": 10.0}
                for h in range(24)
            ]
        }
        advisory = ws.evaluate_spray_advisory(mock_weather, language="en")

        assert advisory["advisory_level"] == "FAVORABLE_WINDOW"
        assert len(advisory["triggered_rules"]) == 0
        assert "Review the product label" in advisory["explanation"]
        # Mandatory limitations notice
        assert "Do not assume spraying is completely safe" in advisory["limitations"]
        assert "buffer zones" in advisory["limitations"]
        assert "KVK" in advisory["limitations"]

    def test_spray_advisory_bilingual_tamil(self):
        ws = WeatherService()
        mock_weather = {
            "current": {"wind_speed": 30.0, "precipitation": 0.0},
            "hourly": [{"precipitation_probability": 20, "precipitation": 0.0, "wind_speed": 30.0}]
        }
        advisory = ws.evaluate_spray_advisory(mock_weather, language="ta")
        assert "காற்றின் வேகம்" in advisory["explanation"]
        assert "மருந்து பாட்டிலின் லேபிளைப் படித்து" in advisory["explanation"]
        assert "KVK" in advisory["limitations"]


class TestCropPathologyRiskContext:
    """Requirement 6: Crop & Disease Risk Context (Module 2 integration)."""

    def test_environmental_risk_analysis_with_scientific_disclaimer(self):
        ws = WeatherService()
        mock_weather = {
            "current": {"temperature": 26.5, "humidity": 88.0, "wind_speed": 12.0, "precipitation": 0.0},
            "hourly": [{"precipitation_probability": 40}]
        }
        risk = ws.get_environmental_risk(mock_weather, crop="Potato", condition="Late Blight", language="en")

        assert risk["risk_level"] in ["Moderate", "High"]
        assert any("humidity" in factor.lower() for factor in risk["environmental_factors"])
        # Scientific disclaimer must state weather alone does NOT prove infection
        assert "do not prove or confirm plant infection" in risk["scientific_disclaimer"].lower()


class TestWeatherAPIEndpoints:
    """Requirement 7: Documented API Endpoints."""

    def test_api_spray_advisory_endpoint(self):
        response = client.get("/api/weather/spray-advisory?lat=11.0168&lon=76.9558")
        assert response.status_code == 200
        data = response.json()

        assert "advisory_level" in data
        assert "triggered_rules" in data
        assert "actual_forecast_values" in data
        assert "threshold_values" in data
        assert "explanation" in data
        assert "limitations" in data
        assert "units" in data
        assert data["threshold_values"]["precipitation_probability_threshold"] == 60
        assert data["threshold_values"]["wind_speed_threshold_kmh"] == 25.0

    def test_api_weather_status_endpoint(self):
        response = client.get("/api/weather/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "Open-Meteo" in data["provider"]
        assert "spray_thresholds" in data
        assert data["spray_thresholds"]["rain_probability_percent"] == 60
