from pydantic import BaseModel, EmailStr
from typing import Optional, List, Union, Any
from datetime import datetime

class UserBase(BaseModel):
    name: str
    mobile: str
    email: Optional[str] = None
    location: Optional[str] = None
    preferred_language: Optional[str] = "en"

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str # mobile or email
    password: str

class UserResponse(UserBase):
    id: Union[int, str]
    model_config = {"from_attributes": True}

class FarmerProfileResponse(BaseModel):
    name: Optional[str] = "Farmer"
    mobile: Optional[str] = None
    location: Optional[str] = None
    farm_size: Optional[float] = None
    primary_crop: Optional[str] = None
    preferred_language: Optional[str] = "en"
    notify_weather: Optional[bool] = True
    notify_spray: Optional[bool] = True
    notify_schemes: Optional[bool] = True

class FarmerProfileUpdate(BaseModel):
    name: Optional[str] = None
    mobile: Optional[str] = None
    location: Optional[str] = None
    farm_size: Optional[float] = None
    primary_crop: Optional[str] = None
    preferred_language: Optional[str] = None
    notify_weather: Optional[bool] = None
    notify_spray: Optional[bool] = None
    notify_schemes: Optional[bool] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TopPrediction(BaseModel):
    class_name: str
    confidence: float
    display_name: Optional[str] = None
    crop: Optional[str] = None
    condition: Optional[str] = None
    raw_score: Optional[float] = None
    is_healthy: Optional[bool] = None

class QualityIssue(BaseModel):
    code: str
    severity: str
    message: str

class QualityAssessment(BaseModel):
    quality_status: str
    quality_score: Optional[float] = None
    detected_issues: List[QualityIssue] = []
    user_facing_message: Optional[str] = None
    photography_tips: List[str] = []
    metrics: Optional[dict] = None

class CropAnalysisBase(BaseModel):
    crop_type: str
    detected_disease: str
    confidence: float
    severity: str
    risk_level: str

class CropAnalysisCreate(CropAnalysisBase):
    image_path: str

class StructuredExplanation(BaseModel):
    # Module 2 Canonical Structured Contract
    summary: Optional[str] = None
    observed_symptoms: Optional[Union[str, List[str]]] = None
    possible_causes: Union[str, List[str]]
    alternative_explanations: Optional[List[str]] = []
    model_prediction_context: Optional[str] = None
    weather_influence: Optional[str] = None
    recommended_next_steps: List[str]
    prevention_guidance: Optional[List[str]] = []
    uncertainty_and_limitations: Optional[str] = None
    kvk_consultation_guidance: Optional[str] = None

    # Preserved Legacy / Backward-Compatible Aliases
    observations: Optional[Union[str, List[str]]] = None
    weather_risk_factor: Optional[str] = None
    why_recommendations: Optional[str] = None
    uncertainty_warnings: Optional[str] = None
    expert_consultation_triggers: Optional[str] = None
    disease_name: Optional[str] = None
    symptoms: Optional[Union[str, List[str]]] = None
    recommendations: Optional[List[str]] = None
    preventive_measures: Optional[List[str]] = None
    model_used: Optional[str] = "Gemma 4"
    language: Optional[str] = "en"
    is_fallback: Optional[bool] = False

class CropAnalysisResponse(BaseModel):
    # Module 1 Contract Fields
    analysis_id: Optional[str] = None
    predicted_class: Optional[str] = None
    display_name: Optional[str] = None
    model_score: Optional[float] = None
    confidence_interpretation: Optional[str] = None
    top_predictions: List[TopPrediction] = []
    quality_assessment: Optional[QualityAssessment] = None
    inconclusive: Optional[bool] = False
    photography_tips: Optional[List[str]] = []
    model_version: Optional[str] = None
    processing_time_ms: Optional[float] = None

    # Preserved Backward-Compatible Fields
    id: Optional[str] = None
    created_at: Optional[str] = None
    crop: str
    condition: str
    confidence: float
    is_healthy: bool
    status: str
    is_inconclusive: Optional[bool] = False
    disease: Optional[str] = None
    severity: Optional[str] = "Not determined"
    risk: Optional[str] = "Not determined"
    quality_status: Optional[str] = "Passed"
    warning_message: Optional[str] = None
    uncertainty_reason: Optional[str] = None
    latency_ms: Optional[float] = None
    preprocessing_mode: Optional[str] = "direct"
    tta_enabled: Optional[bool] = False
    explanation: Optional[StructuredExplanation] = None

class ChatMessage(BaseModel):
    message: str
    language: Optional[str] = "en"
    context: Optional[dict] = None
    conversation_history: Optional[List[dict]] = None

class ChatResponse(BaseModel):
    reply: str
    audio_base64: Optional[str] = None
    explanation: Optional[StructuredExplanation] = None
    detected_language: Optional[str] = "en"
    quick_prompts: Optional[List[str]] = []

class ChatHistoryItem(BaseModel):
    id: str
    role: str
    message: str
    created_at: str

class VoiceChatResponse(BaseModel):
    detected_language: str
    transcription: str
    reply: str
    audio_base64: Optional[str] = None
    explanation: Optional[StructuredExplanation] = None

class MultimodalAnalysisResponse(BaseModel):
    success: bool
    crop_prediction: Optional[CropAnalysisResponse] = None
    explanation: Optional[StructuredExplanation] = None
    weather_context: Optional[dict] = None
    spray_advisory: Optional[str] = None
    recommendation: Optional[str] = None
    audio_base64: Optional[str] = None


