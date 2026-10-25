import os
import sys
from pathlib import Path
try:
    import pytest
except ImportError:
    pytest = None
import numpy as np
from PIL import Image

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.ai.disease_detector import DiseaseDetector
from services.weather_service import WeatherService
from services.weather_alert_service import WeatherAlertService
from api.schemes import AGRICULTURAL_SCHEMES, get_schemes
from config import local_db


class TestDiseaseDetectorQualityAndUncertainty:
    def test_configurable_uncertainty_threshold(self):
        detector_default = DiseaseDetector()
        assert detector_default.uncertainty_threshold == 0.60

        detector_custom = DiseaseDetector(uncertainty_threshold=0.75)
        assert detector_custom.uncertainty_threshold == 0.75

    def test_low_resolution_image_quality_check(self):
        detector = DiseaseDetector()
        # Create small 50x50 image below min_image_width (100)
        img = Image.new("RGB", (50, 50), color=(100, 150, 100))
        status, msg, metrics = detector.check_image_quality(img)
        assert "Low Resolution" in status
        assert msg is not None
        assert "50x50" in msg

    def test_underexposed_image_quality_check(self):
        detector = DiseaseDetector()
        # Create very dark image (mean lum < 40)
        img = Image.new("RGB", (200, 200), color=(10, 15, 10))
        status, msg, metrics = detector.check_image_quality(img)
        assert "Low Light" in status
        assert "underexposed" in msg.lower()

    def test_overexposed_image_quality_check(self):
        detector = DiseaseDetector()
        # Create bright washed-out image
        img = Image.new("RGB", (200, 200), color=(250, 252, 250))
        status, msg, metrics = detector.check_image_quality(img)
        assert "Overexposed" in status
        assert "glare" in msg.lower() or "overexposure" in msg.lower()


class TestWeatherServiceAndAdvisories:
    def test_weather_response_metadata_and_hourly_fields(self):
        ws = WeatherService()
        data = ws.get_weather(11.0168, 76.9558)
        assert data["success"] is True
        assert "units" in data
        assert data["units"]["temperature"] == "°C"
        assert data["units"]["wind_speed"] == "km/h"
        assert "forecast_horizon" in data
        assert "forecast_retrieval_time" in data
        assert "hourly" in data
        assert len(data["hourly"]) > 0

        # Check first hourly record has enriched fields
        first_hour = data["hourly"][0]
        assert "time" in first_hour
        assert "temperature" in first_hour
        assert "relative_humidity" in first_hour
        assert "precipitation_probability" in first_hour
        assert "precipitation" in first_hour
        assert "wind_speed" in first_hour

    def test_environmental_risk_high_humidity_scenario(self):
        ws = WeatherService()
        mock_weather = {
            "current": {"temperature": 27.0, "humidity": 88.0, "wind_speed": 10.0, "precipitation": 0.0},
            "hourly": [{"precipitation_probability": 30}]
        }
        risk = ws.get_environmental_risk(mock_weather, crop="Tomato", condition="Early Blight", language="en")
        assert risk["risk_level"] in ["Moderate", "High"]
        assert any("humidity" in f.lower() for f in risk["environmental_factors"])
        assert "Notice:" in risk["scientific_disclaimer"]

    def test_environmental_risk_tamil_disclaimer(self):
        ws = WeatherService()
        mock_weather = {
            "current": {"temperature": 25.0, "humidity": 92.0, "wind_speed": 15.0, "precipitation": 2.5},
            "hourly": [{"precipitation_probability": 75}]
        }
        risk = ws.get_environmental_risk(mock_weather, crop="Tomato", condition="Late Blight", language="ta")
        assert risk["risk_level"] == "High"
        assert "குறிப்பு:" in risk["scientific_disclaimer"]

    def test_weather_alerts_rain_scenario(self):
        alert_svc = WeatherAlertService()
        forecast = {
            "current": {"time": "2026-10-25T14:00:00"},
            "hourly": {
                "time": [f"2026-10-25T{h:02d}:00:00" for h in range(14, 24)],
                "precipitation_probability": [20, 30, 85, 90, 75, 40, 20, 10, 10, 5],
                "weather_code": [1, 2, 61, 63, 61, 2, 1, 1, 1, 1]
            }
        }
        alerts = alert_svc.generate_alerts(forecast)
        rain_alerts = [a for a in alerts if a["type"] == "rain"]
        assert len(rain_alerts) > 0
        assert rain_alerts[0]["probability"] >= 70
        assert "High Chance of Rain" in rain_alerts[0]["title_en"]
        assert "மழை பெய்ய அதிக வாய்ப்பு" in rain_alerts[0]["title_ta"]

    def test_weather_alerts_thunderstorm_and_hail_scenario(self):
        alert_svc = WeatherAlertService()
        forecast = {
            "current": {"time": "2026-10-25T14:00:00"},
            "hourly": {
                "time": [f"2026-10-25T{h:02d}:00:00" for h in range(14, 20)],
                "precipitation_probability": [40, 50, 60, 60, 50, 40],
                "weather_code": [1, 2, 96, 95, 2, 1] # code 96 has hail
            }
        }
        alerts = alert_svc.generate_alerts(forecast)
        storm_alerts = [a for a in alerts if a["type"] == "thunderstorm"]
        assert len(storm_alerts) > 0
        assert "Hail" in storm_alerts[0]["title_en"] or "Thunderstorm" in storm_alerts[0]["title_en"]

    def test_weather_alerts_calm_scenario(self):
        alert_svc = WeatherAlertService()
        forecast = {
            "current": {"time": "2026-10-25T14:00:00"},
            "hourly": {
                "time": [f"2026-10-25T{h:02d}:00:00" for h in range(14, 20)],
                "precipitation_probability": [5, 10, 15, 10, 5, 5],
                "weather_code": [0, 0, 1, 1, 0, 0]
            }
        }
        alerts = alert_svc.generate_alerts(forecast)
        assert len(alerts) == 0


class TestGovernmentSchemesDirectory:
    def test_all_six_schemes_present(self):
        assert len(AGRICULTURAL_SCHEMES) >= 6
        scheme_names = [s["name"] for s in AGRICULTURAL_SCHEMES]
        assert any("PM-KISAN" in n for n in scheme_names)
        assert any("PMFBY" in n for n in scheme_names)
        assert any("Micro Irrigation" in n or "PMKSY" in n for n in scheme_names)
        assert any("Soil Health Card" in n for n in scheme_names)
        assert any("Kisan Credit Card" in n for n in scheme_names)
        assert any("Kalaignarin" in n for n in scheme_names)

    def test_schemes_have_required_metadata(self):
        for s in AGRICULTURAL_SCHEMES:
            assert "application_steps" in s
            assert "application_steps_ta" in s
            assert "required_documents" in s
            assert "required_documents_ta" in s
            assert "last_verified" in s
            assert "disclaimer" in s
            assert s["source"].startswith("http")

    def test_search_schemes(self):
        res = get_schemes(search="soil")
        assert len(res) >= 1
        assert any("Soil" in s["name"] for s in res)


class TestLocalStorageAndStatsPersistence:
    def test_save_and_stats_cycle(self):
        # Initial stats
        init_stats = local_db.get_crop_stats()
        initial_total = init_stats["total_scans"]

        # Insert a healthy record
        rec_id_healthy = local_db.save_crop_analysis({
            "crop_type": "Tomato",
            "detected_disease": "Tomato healthy",
            "confidence": 0.95,
            "severity": "None",
            "risk_level": "Low",
            "quality_status": "Passed",
            "is_inconclusive": False
        })
        assert rec_id_healthy is not None

        # Insert an inconclusive record
        rec_id_inconclusive = local_db.save_crop_analysis({
            "crop_type": "Potato",
            "detected_disease": "Potato Early blight",
            "confidence": 0.45,
            "severity": "Mild",
            "risk_level": "Moderate",
            "quality_status": "Warning: Mild Blur",
            "is_inconclusive": True
        })
        assert rec_id_inconclusive is not None

        # Verify stats updated
        updated_stats = local_db.get_crop_stats()
        assert updated_stats["total_scans"] == initial_total + 2
        assert updated_stats["healthy_count"] >= init_stats["healthy_count"] + 1
        assert updated_stats["inconclusive_count"] >= init_stats["inconclusive_count"] + 1

        # Delete inserted records and confirm stats decrement
        del_h = local_db.delete_crop_analysis(rec_id_healthy)
        del_i = local_db.delete_crop_analysis(rec_id_inconclusive)
        assert del_h is True
        assert del_i is True

        final_stats = local_db.get_crop_stats()
        assert final_stats["total_scans"] == initial_total
