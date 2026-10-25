import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  AlertTriangle, ArrowLeft, CheckCircle, Bot, ArrowRight, 
  Volume2, VolumeX, Loader2, ChevronDown, ChevronUp, Activity,
  CloudRain, Wind, Droplets, ShieldCheck, Sparkles 
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import WeatherAlerts from '../components/WeatherAlerts';
import { useLocation as useGeoLocation } from '../hooks/useLocation';
import { API_BASE_URL } from '../config/api';

export default function Result() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const { result, imageUrl, isDemo, demoLabel, demoLabelTa } = location.state || {};
  const isTamil = i18n.language === 'ta';
  const apiUrl = API_BASE_URL;

  const { location: geoLoc } = useGeoLocation();
  const [sprayData, setSprayData] = useState(null);

  useEffect(() => {
    if (!geoLoc?.latitude || !geoLoc?.longitude) return;
    const fetchSpray = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/weather/spray-advisory?lat=${geoLoc.latitude}&lon=${geoLoc.longitude}&lang=${isTamil ? 'ta' : 'en'}`);
        if (res.ok) {
          const data = await res.json();
          setSprayData(data);
        }
      } catch (e) {
        console.warn("Spray advisory fetch error:", e);
      }
    };
    fetchSpray();
  }, [geoLoc?.latitude, geoLoc?.longitude, isTamil]);

  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotReply, setCopilotReply] = useState(null);
  const [copilotAudio, setCopilotAudio] = useState(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [activeQuestion, setActiveQuestion] = useState("");
  const [reportId] = useState(() => Math.floor(Date.now() / 1000).toString().slice(-6));
  const audioPlayerRef = useRef(null);

  if (!result) {
    return (
      <div className="text-center p-12 max-w-md mx-auto bg-white rounded-3xl shadow-xs border border-gray-100 my-8">
        <div className="w-16 h-16 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-3">
          <AlertTriangle size={32} />
        </div>
        <h3 className="text-lg font-bold text-gray-800 mb-1">
          {isTamil ? "முடிவுகள் எதுவும் இல்லை" : "No Analysis Results Found"}
        </h3>
        <p className="text-gray-500 text-xs mb-6">
          {isTamil ? "தயவுசெய்து முதலில் ஒரு பயிர் இலையை ஸ்கேன் செய்யவும்." : "Please scan or upload a crop leaf photo first."}
        </p>
        <Link 
          to="/crop" 
          className="inline-flex items-center justify-center gap-2 bg-agronex-primary text-white font-bold px-6 py-3 rounded-2xl shadow-xs hover:bg-agronex-deep transition-all text-xs"
        >
          <span>{isTamil ? "பயிரை ஸ்கேன் செய்க" : "Scan a Crop Leaf"}</span>
          <ArrowRight size={14} />
        </Link>
      </div>
    );
  }

  const { crop, condition, confidence, is_healthy, top_predictions, status, quality_status, warning_message } = result;
  const confPercent = (confidence * 100).toFixed(1);
  const isUncertain = status === "Uncertain" || confidence < 0.60;
  const formattedCondition = (condition || '').replace(/_/g, ' ');

  const handleAskCopilot = async (questionText) => {
    setActiveQuestion(questionText);
    setCopilotLoading(true);
    setCopilotReply(null);
    setCopilotAudio(null);
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      setIsPlayingAudio(false);
    }

    try {
      const res = await fetch(`${apiUrl}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: questionText,
          crop_hint: crop,
          language: i18n.language || 'en',
          context: {
            crop: crop,
            condition: condition,
            confidence: confPercent,
            status: status,
            quality_status: quality_status || "Passed"
          }
        })
      });

      if (res.ok) {
        const data = await res.json();
        setCopilotReply(data);
        if (data.audio_base64) {
          setCopilotAudio(`data:audio/wav;base64,${data.audio_base64}`);
        }
      }
    } catch (err) {
      console.error("Copilot query failed:", err);
    } finally {
      setCopilotLoading(false);
    }
  };

  const toggleAudio = () => {
    if (!copilotAudio) return;
    if (isPlayingAudio && audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      setIsPlayingAudio(false);
    } else {
      const audio = new Audio(copilotAudio);
      audioPlayerRef.current = audio;
      setIsPlayingAudio(true);
      audio.onended = () => setIsPlayingAudio(false);
      audio.onerror = () => setIsPlayingAudio(false);
      audio.play().catch(() => setIsPlayingAudio(false));
    }
  };

  return (
    <div className="max-w-2xl mx-auto pb-12 space-y-6">
      {/* Top Bar with Back Button */}
      <div className="flex items-center justify-between">
        <Link 
          to="/dashboard" 
          className="inline-flex items-center text-xs font-bold text-gray-500 hover:text-agronex-deep transition-colors bg-white px-3 py-1.5 rounded-full border border-gray-100 shadow-xs"
        >
          <ArrowLeft size={14} className="mr-1" />
          <span>{isTamil ? "முகப்புக்குத் திரும்பு" : "Dashboard"}</span>
        </Link>
        <span className="text-[11px] font-semibold text-gray-400">
          ID: #{reportId}
        </span>
      </div>

      {/* Main Diagnostic Card */}
      <div className="bg-white rounded-3xl overflow-hidden shadow-sm border border-gray-100">
        {/* Demonstration Mode Banner if testing reference sample */}
        {isDemo && (
          <div className="bg-blue-50 border-b border-blue-200 px-4 py-2.5 text-xs text-blue-900 flex items-center justify-between shadow-2xs">
            <div className="flex items-center gap-2">
              <span className="text-base">🧪</span>
              <span>
                <strong>{isTamil ? "டெமோ மாதிரி முறை:" : "Demonstration Benchmark Mode:"} </strong>
                {isTamil
                  ? `PlantVillage தொகுப்பிலிருந்து பெறப்பட்ட மாதிரி (${demoLabelTa || demoLabel}). இது மாதிரி ஆய்வுக்கானது, நேரடி பண்ணை முடிவு அல்ல.`
                  : `Evaluating PlantVillage reference sample (${demoLabel}). Demonstration mode for testing, not an on-field diagnosis.`}
              </span>
            </div>
            <span className="font-mono text-[10px] bg-blue-100 text-blue-800 font-bold px-2 py-0.5 rounded uppercase shrink-0">
              DEMO
            </span>
          </div>
        )}

        {/* Status Header Banner */}
        <div className={`p-6 sm:p-8 text-center text-white relative overflow-hidden ${
          is_healthy 
            ? 'bg-gradient-to-br from-emerald-600 via-emerald-700 to-teal-800' 
            : isUncertain 
              ? 'bg-gradient-to-br from-amber-500 via-orange-600 to-amber-700' 
              : 'bg-gradient-to-br from-red-600 via-rose-700 to-amber-800'
        }`}>
          <div className="relative z-10">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/20 text-xs font-bold uppercase tracking-wider backdrop-blur-xs mb-3 border border-white/20">
              {is_healthy 
                ? (isTamil ? "ஆரோக்கியமான பயிர்" : "Healthy Crop") 
                : (isTamil ? "நோய் கண்டறியப்பட்டது" : "Condition Detected")}
            </span>

            <h2 className="text-2xl sm:text-3xl font-black font-display tracking-tight leading-snug">
              {crop}: {formattedCondition}
            </h2>
            <p className="text-white/80 text-xs mt-1 font-medium">
              {status} • {confPercent}% match
            </p>
          </div>
        </div>

        {/* Prediction vs Diagnosis Distinction Notice */}
        <div className="bg-emerald-950/90 text-emerald-100 text-[11px] px-4 py-2 flex items-center justify-between border-b border-emerald-800">
          <span className="font-semibold flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>{isTamil ? "AI காட்சி மாதிரி கணிப்பு (அனுமானம்) — ஆய்வக பரிசோதனை அல்ல" : "AI Visual Hypothesis — Model observation, not a laboratory confirmation"}</span>
          </span>
          <span className="text-[10px] bg-emerald-800/80 px-2 py-0.5 rounded font-mono">
            {result.explanation?.model_used || "Gemma 4"}
          </span>
        </div>

        {/* Low Confidence / Inconclusive Warning Box */}
        {(isUncertain || result.is_inconclusive || result.status === "Inconclusive") && (
          <div className="m-4 p-4 rounded-2xl bg-amber-50 border border-amber-200 flex items-start gap-3 text-xs text-amber-900">
            <AlertTriangle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <strong className="font-bold text-amber-950">
                {isTamil ? "⚠️ தெளிவற்ற பகுப்பாய்வு நிலை (Inconclusive Result)" : "⚠️ Inconclusive Analysis State"}
              </strong>
              <p className="text-amber-800 leading-relaxed">
                {warning_message || result.uncertainty_reason || (isTamil 
                  ? "மாதிரி கணிப்பு உறுதிப்படுத்தப்பட்ட நோய் அல்ல. இலை நிழல் அல்லது தெளிவின்மை காரணமாக துல்லியம் குறைவாக இருக்கலாம். நல்ல வெளிச்சத்தில் மீண்டும் படம் எடுக்கவும்." 
                  : "Visual observation is inconclusive. For safe farming decisions, verify with an agricultural extension officer (KVK) and capture a clearer image with natural sunlight.")}
              </p>
              <div className="text-[11px] text-amber-900/80 pt-1 font-medium">
                Tip: Ensure steady camera focus, natural indirect sunlight, and clean leaf surface without shadows.
              </div>
            </div>
          </div>
        )}

        <div className="p-6 sm:p-8 space-y-6">
          {/* Diagnostic Snapshot with Uploaded Leaf Thumbnail */}
          {imageUrl && (
            <div className="flex items-center gap-4 bg-gray-50 p-3 rounded-2xl border border-gray-100">
              <img src={imageUrl} alt="Crop Leaf" className="w-16 h-16 object-cover rounded-xl border border-gray-200" />
              <div className="flex-1">
                <p className="text-xs font-bold text-gray-800">{crop} Leaf Analysis</p>
                <div className="flex flex-wrap items-center gap-2 mt-0.5">
                  <span className="text-[11px] text-gray-500">
                    Quality: <span className="font-semibold text-emerald-700">{quality_status || "Passed"}</span>
                    {result.quality_assessment?.quality_score !== undefined && (
                      <span className="text-gray-400 font-mono ml-1">({Math.round(result.quality_assessment.quality_score * 100)}%)</span>
                    )}
                  </span>
                  <span className="text-gray-300">•</span>
                  <span className="text-[11px] text-gray-500">
                    Engine: <span className="font-mono text-gray-700">{result.model_version || "EfficientNetV2-S"}</span>
                  </span>
                  {result.latency_ms && (
                    <>
                      <span className="text-gray-300">•</span>
                      <span className="text-[11px] text-gray-400 font-mono">{result.latency_ms} ms</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Model Confidence Bar & Interpretation */}
          <div>
            <div className="flex justify-between text-xs font-bold text-gray-700 mb-1.5">
              <span>Model Prediction Confidence</span>
              <span className="text-agronex-deep font-mono">{confPercent}%</span>
            </div>
            <div className="w-full bg-gray-200 h-2.5 rounded-full overflow-hidden">
              <div 
                className={`h-full rounded-full transition-all duration-1000 ${
                  confidence > 0.85 ? 'bg-emerald-500' : confidence > 0.6 ? 'bg-amber-500' : 'bg-red-500'
                }`}
                style={{ width: `${Math.min(100, Math.max(10, confidence * 100))}%` }}
              />
            </div>
            {result.confidence_interpretation && (
              <p className="text-[11px] text-gray-500 mt-1.5 italic leading-tight">
                ℹ️ {result.confidence_interpretation}
              </p>
            )}
          </div>

          {/* Differential Diagnoses / Alternative Possibilities */}
          {top_predictions && top_predictions.length > 1 && (
            <div className="bg-gray-50/90 p-4 rounded-2xl border border-gray-100 space-y-2">
              <div className="flex justify-between items-center text-xs font-bold text-gray-700">
                <span>{isTamil ? "மாற்று கணிப்புகள் (Differential Diagnoses)" : "Differential Diagnoses"}</span>
                <span className="text-[11px] text-gray-400 font-normal">Top {top_predictions.length} ranked</span>
              </div>
              <div className="space-y-1.5">
                {top_predictions.slice(1, 4).map((pred, idx) => {
                  const pName = (pred.class_name || "").replace(/___/g, " — ").replace(/_/g, " ");
                  const pPct = ((pred.confidence || 0) * 100).toFixed(1);
                  return (
                    <div key={idx} className="flex justify-between items-center text-xs text-gray-600 bg-white p-2 rounded-xl border border-gray-100/80">
                      <span className="truncate pr-2 font-medium">{pName}</span>
                      <span className="font-bold text-gray-700 flex-shrink-0 font-mono">{pPct}%</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ------------------------------------------------------------- */}
          {/* Gemma 4 Explainable AI Section */}
          {/* ------------------------------------------------------------- */}
          {result.explanation && (
            <div className="bg-gradient-to-br from-emerald-50/60 via-green-50/30 to-teal-50/40 p-5 rounded-3xl border border-emerald-200/80 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-emerald-100 pb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-xs">
                    <Sparkles size={16} />
                  </div>
                  <div>
                    <h3 className="font-bold text-agronex-deep text-sm font-display">
                      {isTamil ? "Gemma 4 விளக்கக்கூடிய AI பகுப்பாய்வு" : "Gemma 4 Explainable AI Assessment"}
                    </h3>
                    <p className="text-[11px] text-gray-500">
                      {isTamil ? "காட்சி அறிகுறிகள், காரணங்கள் மற்றும் வானிலை தொடர்பு" : "Visual symptoms, pathological causes & weather interaction"}
                    </p>
                  </div>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full font-mono">
                  Multimodal Copilot
                </span>
              </div>

              {/* 1. Visible Symptoms Observation */}
              <div className="space-y-1 text-xs">
                <span className="font-bold text-emerald-900 flex items-center gap-1.5">
                  🔍 <span>{isTamil ? "கண்டறியப்பட்ட காட்சி அறிகுறிகள்:" : "What the Model Detected & Visual Observations:"}</span>
                </span>
                <p className="text-gray-700 leading-relaxed bg-white/80 p-3 rounded-xl border border-emerald-100/60">
                  {result.explanation.observations}
                </p>
              </div>

              {/* 2. Pathological Causes */}
              <div className="space-y-1 text-xs">
                <span className="font-bold text-emerald-900 flex items-center gap-1.5">
                  🧪 <span>{isTamil ? "சாத்தியமான காரணங்கள் & நுண்ணுயிரிகள்:" : "Possible Pathological Causes:"}</span>
                </span>
                <p className="text-gray-700 leading-relaxed bg-white/80 p-3 rounded-xl border border-emerald-100/60">
                  {result.explanation.possible_causes}
                </p>
              </div>

              {/* 3. Weather Risk Factor */}
              {result.explanation.weather_risk_factor && (
                <div className="space-y-1 text-xs">
                  <span className="font-bold text-emerald-900 flex items-center gap-1.5">
                    🌦️ <span>{isTamil ? "வானிலை தாக்கம் & சுற்றுச்சூழல் அபாயம்:" : "How Weather Affects Disease Risk:"}</span>
                  </span>
                  <p className="text-gray-700 leading-relaxed bg-white/80 p-3 rounded-xl border border-emerald-100/60">
                    {result.explanation.weather_risk_factor}
                  </p>
                </div>
              )}

              {/* 4. Why Recommendations are Suggested */}
              {result.explanation.why_recommendations && (
                <div className="space-y-1 text-xs">
                  <span className="font-bold text-emerald-900 flex items-center gap-1.5">
                    💡 <span>{isTamil ? "பரிந்துரைகளுக்கான அறிவியல் விளக்கம்:" : "Why These Actions are Recommended:"}</span>
                  </span>
                  <p className="text-gray-700 leading-relaxed bg-white/80 p-3 rounded-xl border border-emerald-100/60">
                    {result.explanation.why_recommendations}
                  </p>
                </div>
              )}

              {/* 5. Recommended Next Steps Checklist */}
              {result.explanation.recommended_next_steps && result.explanation.recommended_next_steps.length > 0 && (
                <div className="space-y-1.5 text-xs">
                  <span className="font-bold text-emerald-900 flex items-center gap-1.5">
                    ✅ <span>{isTamil ? "பரிந்துரைக்கப்பட்ட அடுத்த கட்ட நடவடிக்கைகள்:" : "Recommended Safe Next Steps:"}</span>
                  </span>
                  <div className="space-y-1.5">
                    {result.explanation.recommended_next_steps.map((step, sIdx) => (
                      <div key={sIdx} className="flex items-start gap-2 bg-white/90 p-2.5 rounded-xl border border-emerald-100/80 text-gray-700">
                        <CheckCircle size={14} className="text-emerald-600 mt-0.5 flex-shrink-0" />
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 6. Qualified Expert Consultation Triggers */}
              {result.explanation.expert_consultation_triggers && (
                <div className="p-3 bg-amber-50/90 rounded-xl border border-amber-200/80 text-xs text-amber-900 space-y-1">
                  <span className="font-bold flex items-center gap-1.5 text-amber-950">
                    🏛️ <span>{isTamil ? "வேளாண் அலுவலர் / KVK ஆலோசனை பெற வேண்டிய தருணங்கள்:" : "When to Seek Qualified Agronomist (KVK) Advice:"}</span>
                  </span>
                  <p className="text-amber-800 leading-relaxed">
                    {result.explanation.expert_consultation_triggers}
                  </p>
                </div>
              )}
            </div>
          )}


          {/* ------------------------------------------------------------- */}
          {/* Farm Safety & Spray-Condition Advisory Card (Module 3) */}
          {/* ------------------------------------------------------------- */}
          {sprayData && sprayData.advisory_level && (
            <div className={`p-5 rounded-3xl border shadow-xs space-y-3 ${
              sprayData.advisory_level === 'HIGH_RISK'
                ? 'bg-red-50/90 border-red-200 text-red-950'
                : sprayData.advisory_level === 'CAUTION'
                  ? 'bg-amber-50/90 border-amber-200 text-amber-950'
                  : 'bg-emerald-50/90 border-emerald-200 text-emerald-950'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-base">
                    {sprayData.advisory_level === 'HIGH_RISK' ? '🚫' : sprayData.advisory_level === 'CAUTION' ? '⚠️' : '✅'}
                  </span>
                  <span className="text-xs font-bold uppercase tracking-wider">
                    {isTamil ? 'வானிலை & தெளிப்பு பாதுகாப்பு ஆலோசனை' : 'Weather & Spray Safety Advisory (Module 3)'}
                  </span>
                </div>
                <span className={`text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full ${
                  sprayData.advisory_level === 'HIGH_RISK'
                    ? 'bg-red-100 text-red-800'
                    : sprayData.advisory_level === 'CAUTION'
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-emerald-100 text-emerald-800'
                }`}>
                  {sprayData.advisory_level}
                </span>
              </div>

              <p className="text-xs leading-relaxed font-medium">
                {isTamil && sprayData.explanation_ta ? sprayData.explanation_ta : sprayData.explanation}
              </p>

              {sprayData.triggered_rules && sprayData.triggered_rules.length > 0 && (
                <div className="space-y-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider opacity-75">
                    {isTamil ? 'தூண்டப்பட்ட எச்சரிக்கைகள்:' : 'Active Caution Triggers:'}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {sprayData.triggered_rules.map((rule, idx) => (
                      <span key={idx} className="bg-white/80 border border-current text-[11px] font-semibold px-2 py-0.5 rounded-md">
                        {rule}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {sprayData.actual_forecast_values && (
                <div className="grid grid-cols-3 gap-2 pt-2 border-t border-black/5 text-[11px]">
                  <div className="bg-white/70 p-2 rounded-xl">
                    <span className="block text-[10px] opacity-70">Wind Speed</span>
                    <strong>{sprayData.actual_forecast_values.wind_speed_kmh ?? '--'} km/h</strong>
                  </div>
                  <div className="bg-white/70 p-2 rounded-xl">
                    <span className="block text-[10px] opacity-70">Rain Prob</span>
                    <strong>{sprayData.actual_forecast_values.rain_probability_pct ?? '--'}%</strong>
                  </div>
                  <div className="bg-white/70 p-2 rounded-xl">
                    <span className="block text-[10px] opacity-70">Precipitation</span>
                    <strong>{sprayData.actual_forecast_values.precipitation_mm ?? '--'} mm</strong>
                  </div>
                </div>
              )}

              <p className="text-[10px] opacity-75 pt-1 border-t border-black/5 leading-tight">
                {sprayData.limitations || "Favorable weather conditions do not guarantee spraying is universally safe. Applicators must consult chemical product labels, crop growth stage, and buffer zones."}
              </p>
            </div>
          )}

          {/* ------------------------------------------------------------- */}
          {/* AgroNex AI Copilot Grounded Follow-up Section */}
          {/* ------------------------------------------------------------- */}
          <div className="bg-gradient-to-br from-emerald-50/70 via-teal-50/40 to-slate-50 p-5 rounded-3xl border border-emerald-200/80 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-xs">
                  <Bot size={18} />
                </div>
                <div>
                  <h4 className="font-bold text-agronex-deep text-sm font-display">
                    {t('copilot_title')}
                  </h4>
                  <p className="text-[11px] text-gray-500">
                    {t('copilot_subtitle')}
                  </p>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full">
                AgentFoundry v1.0
              </span>
            </div>

            {/* Quick Prompt Pills */}
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                onClick={() => handleAskCopilot(t('ask_spray'))}
                disabled={copilotLoading}
                className="text-xs px-3 py-1.5 bg-white hover:bg-emerald-600 hover:text-white text-emerald-800 font-semibold rounded-full border border-emerald-200 shadow-2xs transition-all disabled:opacity-50"
              >
                💧 {t('ask_spray')}
              </button>
              <button
                onClick={() => handleAskCopilot(t('ask_organic'))}
                disabled={copilotLoading}
                className="text-xs px-3 py-1.5 bg-white hover:bg-emerald-600 hover:text-white text-emerald-800 font-semibold rounded-full border border-emerald-200 shadow-2xs transition-all disabled:opacity-50"
              >
                🌿 {t('ask_organic')}
              </button>
              <button
                onClick={() => handleAskCopilot(t('ask_prevention'))}
                disabled={copilotLoading}
                className="text-xs px-3 py-1.5 bg-white hover:bg-emerald-600 hover:text-white text-emerald-800 font-semibold rounded-full border border-emerald-200 shadow-2xs transition-all disabled:opacity-50"
              >
                🛡️ {t('ask_prevention')}
              </button>
            </div>

            {/* Loading Indicator */}
            {copilotLoading && (
              <div className="flex items-center gap-2 p-4 bg-white/80 rounded-2xl border border-emerald-100 text-xs text-emerald-800 font-medium animate-pulse">
                <Loader2 size={16} className="animate-spin text-emerald-600" />
                <span>AgroNex Agent is evaluating local weather and agricultural rules...</span>
              </div>
            )}

            {/* Copilot Result Box */}
            {copilotReply && (
              <div className="bg-white p-4 sm:p-5 rounded-2xl border border-emerald-100 shadow-xs space-y-3">
                <div className="flex items-start justify-between gap-2 border-b border-gray-100 pb-2">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-emerald-700 tracking-wider">
                      Agent Consultation
                    </span>
                    <p className="text-xs font-bold text-gray-800 mt-0.5">"{activeQuestion}"</p>
                  </div>
                  {copilotAudio && (
                    <button
                      onClick={toggleAudio}
                      className="flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-full text-xs font-bold transition-colors"
                    >
                      {isPlayingAudio ? <VolumeX size={14} /> : <Volume2 size={14} />}
                      <span>{isPlayingAudio ? "Pause" : "Listen"}</span>
                    </button>
                  )}
                </div>

                {/* Spray Window Banner */}
                {copilotReply.spray_advisory && (
                  <div className={`p-2.5 rounded-xl text-xs font-bold flex items-center gap-2 ${
                    copilotReply.spray_advisory.includes("DO NOT") 
                      ? "bg-red-50 text-red-800 border border-red-200"
                      : "bg-emerald-50 text-emerald-800 border border-emerald-200"
                  }`}>
                    <span>⚡</span>
                    <span>{copilotReply.spray_advisory}</span>
                  </div>
                )}

                {/* Recommendation Text */}
                <p className="text-xs sm:text-sm text-gray-700 whitespace-pre-line leading-relaxed font-normal">
                  {copilotReply.recommendation}
                </p>

                {/* Collapsible Execution Trace for Hackathon Transparency */}
                {copilotReply.execution_trace && (
                  <div className="pt-2 border-t border-gray-100">
                    <button
                      onClick={() => setShowTrace(!showTrace)}
                      className="flex items-center justify-between w-full text-[11px] font-bold text-gray-500 hover:text-emerald-700"
                    >
                      <span className="flex items-center gap-1">
                        <Activity size={12} className="text-emerald-600" />
                        {t('workflow_trace')} ({copilotReply.total_latency_ms} ms)
                      </span>
                      {showTrace ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    {showTrace && (
                      <div className="mt-2 p-3 bg-gray-50 rounded-xl space-y-1.5 text-[11px] text-gray-600 font-mono">
                        {copilotReply.execution_trace.map((step, idx) => (
                          <div key={idx} className="flex justify-between items-center border-b border-gray-200/50 pb-1 last:border-none">
                            <span className="font-semibold text-gray-800">{step.node}</span>
                            <span>{step.duration_ms} ms • {step.status}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* CTA: Full Conversational Voice Assistant */}
          <Link 
            to="/assistant" 
            state={{ initialCropContext: result }}
            className="flex items-center justify-between p-4 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-700 text-white transition-all shadow-md hover:shadow-lg group"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-white/20 text-white flex items-center justify-center shadow-xs">
                <Bot size={20} />
              </div>
              <div>
                <h4 className="font-bold text-sm leading-tight">
                  {isTamil ? "முழு குரல் வழிகாட்டலுக்கு அக்ரோநெக்ஸ் உதவியாளர்" : "Open Full Voice Copilot Assistant"}
                </h4>
                <p className="text-[11px] text-emerald-100/90 font-medium">
                  {isTamil ? "நேரடி தமிழ் குரல் உரையாடல் மற்றும் ஆலோசனைகள்" : "Speak naturally in Tamil or English with live microphone"}
                </p>
              </div>
            </div>
            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
          </Link>

          {/* Weather Alerts Module */}
          <div className="pt-2">
            <WeatherAlerts crop={crop} condition={condition} />
          </div>

          {/* Scientific Disclaimer & Qualified Guidance Priority */}
          <div className="p-3.5 bg-gray-50 rounded-2xl border border-gray-200/70 text-[11px] text-gray-500 leading-relaxed">
            <strong className="text-gray-700 block mb-0.5">
              {isTamil ? 'அறிவியல் மற்றும் ஒழுங்குமுறை அறிவிப்பு:' : 'Scientific & Regulatory Notice:'}
            </strong>
            {isTamil
              ? 'கணினி பார்வை மாதிரி முடிவுகள் ஆரம்பகட்ட கள வழிகாட்டலுக்கு மட்டுமே. இது ஆய்வக உறுதிப்படுத்தல் அல்ல. பூச்சிக்கொல்லி மருந்துகளைப் பயன்படுத்துவதற்கு முன் அதிகாரப்பூர்வ தயாரிப்பு லேபிள் வழிமுறைகள், பாதுகாப்பு இடைவெளிகள் மற்றும் வட்டார வேளாண் பல்கலைக்கழகம்/KVK விஞ்ஞானிகளின் வழிகாட்டலைப் பின்பற்றவும்.'
              : 'Computer vision observation is an auxiliary decision aid and not a laboratory diagnosis. Prioritize registered pesticide label instructions, safety intervals (PHI), protective gear (PPE), and qualified Krishi Vigyan Kendra (KVK) extension officer recommendations.'}
          </div>
        </div>
      </div>
    </div>
  );
}
