from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, Any
from services.weather_service import WeatherService, validate_coordinates
from config.weather_thresholds import (
    SPRAY_RAIN_PROB_THRESHOLD,
    SPRAY_PRECIP_THRESHOLD_MM,
    SPRAY_WIND_SPEED_THRESHOLD_KMH,
)

router = APIRouter()
weather_service = WeatherService()


@router.get("/")
@router.get("/forecast")
async def get_forecast(
    lat: float = Query(..., description="Latitude in decimal degrees (-90 to 90)"),
    lon: float = Query(..., description="Longitude in decimal degrees (-180 to 180)"),
    crop: Optional[str] = Query(None, description="Optional crop name for alert evaluation"),
    condition: Optional[str] = Query(None, description="Optional condition name for alert evaluation"),
    language: Optional[str] = Query("en", description="Language code ('en' or 'ta')"),
    location_source: Optional[str] = Query(None, description="Source of coordinates ('user_coordinates', 'manual_selection', 'district_preset')"),
    location_name: Optional[str] = Query(None, description="Human-readable city/district label")
) -> Dict[str, Any]:
    """
    Retrieves real-time Open-Meteo numerical weather forecast.
    Includes 24-hour hourly resolution, 7-day outlook, units, retrieval timestamps,
    and embedded spray-condition advisory evaluation.
    """
    try:
        valid_lat, valid_lon = validate_coordinates(lat, lon)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    result = weather_service.get_weather(
        lat=valid_lat,
        lon=valid_lon,
        crop=crop,
        condition=condition,
        location_source=location_source,
        location_name=location_name,
        language=language or "en"
    )

    if not result.get("success"):
        raise HTTPException(status_code=503, detail=result.get("error", "Weather service temporarily unavailable."))

    return result


@router.get("/spray-advisory")
@router.get("/advisory")
async def get_spray_advisory(
    lat: float = Query(..., description="Latitude in decimal degrees (-90 to 90)"),
    lon: float = Query(..., description="Longitude in decimal degrees (-180 to 180)"),
    rain_prob_threshold: Optional[float] = Query(None, description="Custom precipitation probability threshold % (default: 60)"),
    precip_threshold: Optional[float] = Query(None, description="Custom precipitation amount threshold mm (default: 2.0)"),
    wind_threshold: Optional[float] = Query(None, description="Custom wind speed threshold km/h (default: 25.0)"),
    language: Optional[str] = Query("en", description="Language code ('en' or 'ta')")
) -> Dict[str, Any]:
    """
    Module 3 / Section 5 Spray-Condition Advisory Engine.
    Evaluates upcoming 24-hour forecast window against configurable caution thresholds:
    - Precipitation probability > 60%
    - Forecast precipitation > 2.0 mm
    - Wind speed > 25.0 km/h
    Returns triggered_rules, actual_forecast_values, threshold_values, explanation,
    advisory_level, missing_information, and explicit agronomic limitations.
    """
    try:
        valid_lat, valid_lon = validate_coordinates(lat, lon)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    forecast = weather_service.get_weather(lat=valid_lat, lon=valid_lon, language=language or "en")
    if not forecast.get("success"):
        raise HTTPException(status_code=503, detail=forecast.get("error", "Weather forecast unavailable."))

    advisory = weather_service.evaluate_spray_advisory(
        weather_data=forecast,
        rain_prob_threshold=rain_prob_threshold or SPRAY_RAIN_PROB_THRESHOLD,
        precip_threshold_mm=precip_threshold or SPRAY_PRECIP_THRESHOLD_MM,
        wind_speed_threshold_kmh=wind_threshold or SPRAY_WIND_SPEED_THRESHOLD_KMH,
        language=language or "en"
    )
    return {
        "location": forecast.get("location"),
        "retrieval_timestamp": forecast.get("forecast_retrieval_time"),
        "data_source": forecast.get("data_source"),
        **advisory
    }


@router.get("/risk")
async def get_crop_weather_risk(
    lat: float = Query(..., description="Latitude in decimal degrees (-90 to 90)"),
    lon: float = Query(..., description="Longitude in decimal degrees (-180 to 180)"),
    crop: Optional[str] = Query(None, description="Crop name"),
    condition: Optional[str] = Query(None, description="Pathology condition name"),
    language: Optional[str] = Query("en", description="Language code ('en' or 'ta')")
) -> Dict[str, Any]:
    """
    Evaluates micro-climate environmental favorability for crop/disease pathology.
    Grounded in plant pathology; explicitly disclaims that weather alone proves infection.
    """
    try:
        valid_lat, valid_lon = validate_coordinates(lat, lon)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    forecast = weather_service.get_weather(valid_lat, valid_lon, crop, condition, language=language or "en")
    if not forecast.get("success"):
        raise HTTPException(status_code=503, detail=forecast.get("error", "Weather forecast unavailable."))

    return weather_service.get_environmental_risk(
        weather_data=forecast,
        crop=crop,
        condition=condition,
        language=language or "en"
    )


@router.get("/status")
def get_weather_service_status() -> Dict[str, Any]:
    """
    Diagnostic status of Weather Intelligence Service and Open-Meteo integration.
    """
    return {
        "status": "operational",
        "service": "AgroNex Weather Intelligence Engine (Module 3)",
        "provider": "Open-Meteo Numerical Weather API",
        "api_endpoint": "https://api.open-meteo.com/v1/forecast",
        "cache_ttl_seconds": weather_service.cache_ttl,
        "cached_locations_count": len(weather_service._cache),
        "spray_thresholds": {
            "rain_probability_percent": SPRAY_RAIN_PROB_THRESHOLD,
            "precipitation_mm": SPRAY_PRECIP_THRESHOLD_MM,
            "wind_speed_kmh": SPRAY_WIND_SPEED_THRESHOLD_KMH
        },
        "supported_languages": ["en", "ta"]
    }
