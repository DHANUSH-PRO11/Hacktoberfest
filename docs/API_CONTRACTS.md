# AgroNex AI — API Integration Contracts & Service Interfaces

## 1. Architecture & Service Topology

AgroNex AI coordinates five specialized domains:
1. **Crop Intelligence Service (`/api/crops`)**: Optical quality gating, EfficientNetV2-S ONNX leaf classification, diagnostic uncertainty interpretation.
2. **Gemma AI Multimodal Service (`/api/assistant`)**: Multimodal leaf symptom reasoning, grounded bilingual Tamil/English recommendations, conversational audio synthesis.
3. **Weather Intelligence Service (`/api/weather`)**: Real-time Open-Meteo micro-climate retrieval, 24-hour hourly forecast, spray caution evaluation.
4. **AgroNex Copilot Agent (`/api/agent`)**: AgentFoundry 10-step multi-node autonomous agricultural workflow.
5. **Persistence & Directory Services (`/api/profile`, `/api/schemes`, `/health`)**: Farmer profile synchronization, verified government subsidy directory, system health telemetry.

---

## 2. API Endpoint Specifications

### 2.1 Crop Disease Analysis
- **Route**: `POST /api/crops/analyze`
- **Content-Type**: `multipart/form-data`
- **Request Parameters**:
  | Parameter | Type | Required | Description |
  | :--- | :--- | :--- | :--- |
  | `file` | File binary | Yes | Leaf image (JPEG, PNG, WebP), max 10 MB |
  | `mode` | String | No | Preprocessing mode (`"direct"` or `"letterbox"`, default: `"direct"`) |
  | `enable_tta` | Boolean | No | Test-Time Augmentation (default: `false`) |
  | `explain` | Boolean | No | Generate structured Gemma 4 explanation (default: `true`) |
  | `language` | String | No | Language code (`"en"` or `"ta"`, default: `"en"`) |
  | `latitude` | Float | No | Field latitude for weather grounding |
  | `longitude` | Float | No | Field longitude for weather grounding |
- **Success Response (`200 OK`)**:
  ```json
  {
    "analysis_id": "b78b5e92-3c81-42e8-b80a-995f5cf21682",
    "crop": "Tomato",
    "condition": "Early_Blight",
    "display_name": "Tomato: Early Blight",
    "confidence": 0.892,
    "is_healthy": false,
    "status": "High confidence",
    "is_inconclusive": false,
    "severity": "Moderate",
    "risk": "High",
    "quality_status": "Passed",
    "top_predictions": [
      {
        "class_name": "Tomato___Early_blight",
        "confidence": 0.892,
        "crop": "Tomato",
        "condition": "Early_Blight",
        "is_healthy": false
      }
    ],
    "explanation": {
      "summary": "Target-like concentric ring lesions observed on tomato foliage.",
      "observed_symptoms": ["Dark brown spots with concentric circles", "Surrounding chlorotic halo"],
      "possible_causes": ["Alternaria solani fungal pathogen", "Warm humid weather"],
      "recommended_next_steps": ["Prune lower infected leaves", "Apply biological Trichoderma viride", "Avoid overhead irrigation"],
      "weather_influence": "High ambient humidity (85%) accelerates fungal sporulation.",
      "uncertainty_and_limitations": "Visual symptoms may resemble Septoria spot under early progression.",
      "kvk_consultation_guidance": "Consult local Krishi Vigyan Kendra if defoliation exceeds 25% of canopy."
    }
  }
  ```
- **Error Codes**:
  - `400 Bad Request`: Empty file, invalid magic bytes, or corrupted image.
  - `413 Payload Too Large`: Image file exceeds 10 MB limit.
  - `500 Internal Server Error`: Diagnostic model failure.

---

### 2.2 Crop Analysis History & Deletion
- **Retrieve History**: `GET /api/crops/history?limit=50&offset=0`
  - **Response (`200 OK`)**: Array of `CropAnalysisResponse` objects sorted by `created_at DESC`.
- **Delete Record**: `DELETE /api/crops/history/{record_id}`
  - **Response (`200 OK`)**: `{"success": true, "message": "Record deleted successfully"}`
  - **Error (`404 Not Found`)**: Analysis record does not exist.
  - **Side-Effect**: Automatically decrements dashboard stats and cleans up associated temporary uploads.
- **Dashboard Stats**: `GET /api/crops/stats`
  - **Response (`200 OK`)**:
    ```json
    {
      "total_scans": 24,
      "healthy_count": 18,
      "condition_alerts": 5,
      "inconclusive_count": 1
    }
    ```

---

### 2.3 Gemma AI Multimodal Assistant
- **Text Chat**: `POST /api/assistant/chat`
  - **Body (`application/json`)**:
    ```json
    {
      "message": "How do I manage tomato early blight organically?",
      "language": "en",
      "context": {"crop": "Tomato", "condition": "Early_Blight"}
    }
    ```
  - **Response (`200 OK`)**:
    ```json
    {
      "reply": "For organic control of Tomato Early Blight, implement drip irrigation to avoid leaf wetness, apply neem oil (5ml/L) or Trichoderma viride, and destroy lower infected leaves.",
      "audio_base64": null,
      "detected_language": "en",
      "quick_prompts": [
        "What are the organic remedies for this?",
        "Is it safe to spray today?",
        "Government subsidies for pest management"
      ]
    }
    ```
- **Multimodal Chat (Image + Text)**: `POST /api/assistant/multimodal`
  - Form-data: `image` (UploadFile), `query` (string), `language` (`"en"` or `"ta"`), `latitude`, `longitude`.
- **Voice Chat**: `POST /api/assistant/voice`
  - Form-data: `file` (audio binary, e.g. WAV/WebM), `language` (`"ta"` or `"en"`).
  - Returns: `{"detected_language": "ta", "transcription": "...", "reply": "...", "audio_base64": "..."}`.
- **Model Verification Telemetry**: `GET /api/assistant/model-info`
  - Returns real-time active model identifier, API key availability, and fallback engine status.

---

### 2.4 Weather Intelligence Service
- **Forecast**: `GET /api/weather/forecast?lat=11.0168&lon=76.9558&language=en`
  - Returns current conditions, 24h hourly forecast array, 7-day outlook, units, and retrieval timestamps.
- **Spray Advisory**: `GET /api/weather/spray-advisory?lat=11.0168&lon=76.9558&language=en`
  - Evaluates:
    - Rain probability $\le 60\%$
    - Forecast precipitation $\le 2.0\text{ mm}$
    - Wind speed $\le 25.0\text{ km/h}$
  - Returns: `advisory_level` (`"favorable"`, `"caution"`, `"unsafe"`), `triggered_rules`, and agronomic explanation.

---

### 2.5 Government Schemes Directory
- **Route**: `GET /api/schemes?lang=en&search=kisan&scheme_type=Central`
- **Response (`200 OK`)**: Array of verified scheme entries with verified fields:
  - `name`, `name_ta`
  - `scheme_type` ("Central Government Scheme" vs. "State Government Scheme")
  - `purpose`, `purpose_ta`
  - `benefits`, `benefits_ta`
  - `eligibility`, `eligibility_ta`
  - `application_steps`, `application_steps_ta`
  - `required_documents`, `required_documents_ta`
  - `official_portal` (validated https link)
  - `last_verified` ("October 2026")
  - `disclaimer` (statutory non-guarantee notice)

---

### 2.6 Health Check Telemetry
- **Liveness Probe**: `GET /health` or `GET /api/health`
  - Returns: `{"status": "ok"}`
- **Full Module Telemetry**: `GET /health?detail=true`
  - Returns:
    ```json
    {
      "status": "ok",
      "service": "AgroNex AI Platform Engine (Module 5)",
      "version": "1.0.0",
      "environment": "development",
      "components": {
        "database": "connected",
        "crop_engine": "operational",
        "weather_engine": "operational",
        "gemma_assistant": "operational",
        "schemes_directory": "operational"
      }
    }
    ```

---

## 3. Standard Error Envelope
All error responses return structured JSON:
```json
{
  "detail": "Descriptive human-readable explanation of error condition."
}
```
HTTP Status Codes:
- `400`: Invalid client input (e.g. non-image file, missing required parameters).
- `401`: Missing or invalid Bearer authentication token.
- `404`: Entity not found.
- `413`: Payload exceeds maximum allowed size (10 MB).
- `422`: Unprocessable Entity (e.g., coordinates out of range).
- `503`: External provider temporarily unavailable (e.g. Open-Meteo downtime).
- `500`: Internal application error.
