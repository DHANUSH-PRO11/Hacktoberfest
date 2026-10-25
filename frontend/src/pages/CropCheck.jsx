import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Camera, Image as ImageIcon, CheckCircle, AlertTriangle, Sparkles, RefreshCw, ArrowRight, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '../config/api';

export default function CropCheck() {
  const { t, i18n } = useTranslation();
  const [image, setImage] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const navigate = useNavigate();

  const [fileObj, setFileObj] = useState(null);
  const isTamil = i18n.language === 'ta';

  const [demoSample, setDemoSample] = useState(null);

  const clearImage = () => {
    setImage(null);
    setFileObj(null);
    setDemoSample(null);
    setErrorMsg(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (cameraInputRef.current) cameraInputRef.current.value = '';
  };

  const handleImageFile = (file, isDemoObj = null) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setErrorMsg("Please upload an image file (JPG, PNG, WEBP).");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setErrorMsg(isTamil ? "கோப்பின் அளவு 10 MB க்கும் குறைவாக இருக்க வேண்டும்." : "Image file exceeds maximum allowed size of 10 MB.");
      return;
    }
    setErrorMsg(null);
    setFileObj(file);
    setDemoSample(isDemoObj);
    const img = URL.createObjectURL(file);
    setImage(img);
  };

  const handleImageUpload = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleImageFile(e.target.files[0], null);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleImageFile(e.dataTransfer.files[0], null);
    }
  };

  const loadSampleImage = async (sample) => {
    try {
      setErrorMsg(null);
      const res = await fetch(sample.path);
      if (!res.ok) throw new Error("Sample file not found");
      const blob = await res.blob();
      const file = new File([blob], sample.file, { type: sample.mime });
      handleImageFile(file, sample);
    } catch (err) {
      console.warn("Could not load sample:", err);
      setErrorMsg(isTamil ? "மாதிரி படத்தை ஏற்றுவதில் சிக்கல்." : "Could not load sample image.");
    }
  };

  const analyze = async () => {
    if (!fileObj) return;
    setAnalyzing(true);
    setErrorMsg(null);
    
    const formData = new FormData();
    formData.append('file', fileObj);
    formData.append('explain', 'true');
    formData.append('language', i18n.language || 'en');
    
    try {
      const apiUrl = API_BASE_URL;
      const response = await fetch(`${apiUrl}/api/crops/analyze`, {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        const data = await response.json();
        navigate('/result', { 
          state: { 
            result: data, 
            imageUrl: image,
            isDemo: Boolean(demoSample),
            demoLabel: demoSample?.name,
            demoLabelTa: demoSample?.ta
          } 
        });
      } else {
        const errJson = await response.json().catch(() => ({}));
        setErrorMsg(errJson.detail || (isTamil ? "படத்தை பகுப்பாய்வு செய்ய முடியவில்லை. தெளிவான இலையின் படத்தை பதிவேற்றவும்." : "Unable to analyze this image. Please provide a clear leaf photo."));
      }
    } catch (error) {
      console.error('API Error:', error);
      setErrorMsg(isTamil ? "சேவையகத்துடன் இணைக்க முடியவில்லை." : "Unable to connect to analysis server. Please check backend connection.");
    } finally {
      setAnalyzing(false);
    }
  };


  return (
    <div className="space-y-6 max-w-xl mx-auto pb-10">
      {/* Title & Badge */}
      <div className="text-center mt-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100/80 text-emerald-800 text-xs font-bold mb-2 border border-emerald-200/60">
          <Sparkles size={13} className="text-emerald-600" />
          <span>{isTamil ? "AI பயிர் நோய் கண்டறிதல்" : "AI Crop Pathology Engine"}</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-agronex-deep font-display tracking-tight">
          {t('check_crop_title')}
        </h1>
        <p className="text-gray-500 text-sm mt-1 max-w-md mx-auto">
          {t('check_crop_subtitle')}
        </p>
      </div>

      {!image ? (
        <div className="space-y-6">
          {/* Hidden file inputs */}
          <input
            type="file"
            ref={cameraInputRef}
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={handleImageUpload}
          />
          <input
            type="file"
            ref={fileInputRef}
            accept="image/*"
            className="hidden"
            onChange={handleImageUpload}
          />

          {/* Interactive Upload / Dropzone Area */}
          <div 
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-3xl p-8 sm:p-10 text-center transition-all bg-white relative overflow-hidden ${
              isDragging 
                ? 'border-emerald-500 bg-emerald-50/50 scale-[1.01]' 
                : 'border-emerald-200 hover:border-emerald-400 hover:bg-emerald-50/30'
            }`}
          >
            <div className="w-18 h-18 bg-gradient-to-br from-emerald-100 to-green-100 rounded-3xl flex items-center justify-center mx-auto mb-4 text-emerald-700 shadow-xs">
              <Camera size={36} className="text-emerald-700" />
            </div>

            <h3 className="text-lg font-bold text-agronex-deep mb-1 font-display">
              {isTamil ? "பயிர் இலையை புகைப்படம் எடுக்கவும் அல்லது பதிவேற்றவும்" : "Capture or Upload Crop Leaf"}
            </h3>
            <p className="text-xs text-gray-500 max-w-xs mx-auto mb-6">
              {isTamil ? "நேரடி கேமரா அல்லது கேலரி மூலம் தெளிவான இலையின் படத்தை சமர்ப்பிக்கவும்" : "Supports Tomato, Potato, Pepper, Paddy, Cotton, Grape & more"}
            </p>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 max-w-sm mx-auto">
              <button
                type="button"
                onClick={() => cameraInputRef.current?.click()}
                className="w-full sm:w-auto bg-agronex-primary hover:bg-agronex-deep text-white px-6 py-3 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-sm hover:scale-[1.02] active:scale-[0.98] transition-all text-sm"
              >
                <Camera size={18} />
                <span>{t('take_photo')}</span>
              </button>

              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-full sm:w-auto bg-emerald-50 hover:bg-emerald-100 text-emerald-900 border border-emerald-200/80 px-5 py-3 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all text-sm"
              >
                <ImageIcon size={18} />
                <span>{t('upload_image')}</span>
              </button>
            </div>

            <div className="mt-6 pt-4 border-t border-gray-100 text-[11px] text-gray-400 font-medium">
              JPG, PNG, WEBP • Max 10MB
            </div>
          </div>

          {/* Quick Demo: Sample Leaf Images */}
          <div className="bg-white p-5 rounded-3xl shadow-xs border border-gray-100 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
                <Sparkles size={14} className="text-emerald-600" />
                <span>{isTamil ? "சோதனை மாதிரி இலைகள் (கிளிக் செய்து பரிசோதிக்கவும்)" : "Demo Sample Leaf Images (Click to Test)"}</span>
              </span>
              <span className="text-[10px] bg-emerald-50 text-emerald-800 font-bold px-2 py-0.5 rounded-full border border-emerald-200/60">
                PlantVillage CC-BY 4.0
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {[
                { name: "Tomato Early Blight", ta: "தக்காளி இலைக்கருகல்", path: "/samples/tomato_early_blight.jpg", file: "tomato_early_blight.jpg", mime: "image/jpeg", badge: "Early Blight" },
                { name: "Potato Late Blight", ta: "உருளை இலைக்கருகல்", path: "/samples/potato_late_blight.jpg", file: "potato_late_blight.jpg", mime: "image/jpeg", badge: "Late Blight" },
                { name: "Healthy Corn Leaf", ta: "ஆரோக்கிய சோள இலை", path: "/samples/healthy_corn.png", file: "healthy_corn.png", mime: "image/png", badge: "Healthy" },
                { name: "Pepper Bacterial Spot", ta: "மிளகாய் பாக்டீரியா புள்ளி", path: "/samples/pepper_bacterial_spot.webp", file: "pepper_bacterial_spot.webp", mime: "image/webp", badge: "Bacterial Spot" }
              ].map((sample, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => loadSampleImage(sample)}
                  className="p-2.5 rounded-2xl bg-gray-50 hover:bg-emerald-50/70 border border-gray-200/70 hover:border-emerald-300 text-left transition-all group flex flex-col justify-between cursor-pointer"
                >
                  <div className="w-full h-16 rounded-xl overflow-hidden mb-2 bg-gray-200 border border-gray-100 flex items-center justify-center">
                    <img src={sample.path} alt={sample.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-emerald-800 block truncate">{sample.badge}</span>
                    <span className="text-[11px] font-medium text-gray-700 block truncate">{isTamil ? sample.ta : sample.name}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Leaf Photography Checklist Card */}
          <div className="bg-white p-5 sm:p-6 rounded-3xl shadow-xs border border-gray-100">
            <h3 className="font-bold text-agronex-deep text-sm mb-3 flex items-center gap-2">
              <ShieldCheck size={18} className="text-emerald-600" />
              <span>{t('instructions')}</span>
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {[
                t('inst_1'),
                t('inst_2'),
                t('inst_3'),
                t('inst_4')
              ].map((inst, idx) => (
                <div key={idx} className="flex items-center gap-2.5 p-2 rounded-xl bg-gray-50/70 border border-gray-100 text-xs font-semibold text-gray-700">
                  <CheckCircle size={15} className="text-emerald-500 flex-shrink-0" />
                  <span>{inst.replace(/^[✓✔]\s*/, '')}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* Image Preview & Scan Mode */
        <div className="space-y-4 animate-in fade-in zoom-in duration-300">
          {/* Demonstration Sample Banner if in Demo Mode */}
          {demoSample && (
            <div className="bg-blue-50 border border-blue-200 px-4 py-2.5 rounded-2xl flex items-center justify-between text-xs text-blue-900 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="text-sm">🧪</span>
                <span>
                  <strong>{isTamil ? "மாதிரி டெமோ பயன்முறை:" : "Demonstration Mode:"} </strong>
                  {isTamil ? `PlantVillage குறிப்பு மாதிரி (${demoSample.ta}). நேரடி பண்ணை படம் அல்ல.` : `PlantVillage benchmark sample (${demoSample.name}). For test demonstration only.`}
                </span>
              </div>
              <span className="text-[10px] bg-blue-100 text-blue-800 font-mono font-bold px-2 py-0.5 rounded shrink-0">
                DEMO
              </span>
            </div>
          )}

          <div className="relative rounded-3xl overflow-hidden shadow-lg border-2 border-emerald-200 bg-black">
            <img src={image} alt="Crop Leaf Preview" className="w-full h-80 sm:h-96 object-cover" />
            
            {/* Visual Laser Scanline during active analysis */}
            {analyzing && (
              <>
                <div className="absolute inset-0 bg-emerald-900/40 backdrop-blur-xs flex flex-col items-center justify-center z-20">
                  <div className="w-16 h-16 border-4 border-white/20 border-t-emerald-400 rounded-full animate-spin mb-3"></div>
                  <p className="font-bold text-white text-base tracking-wide flex items-center gap-2">
                    <Sparkles size={16} className="text-emerald-300 animate-pulse" />
                    <span>{isTamil ? "AI நோயை பகுப்பாய்வு செய்கிறது..." : "AI Analyzing Crop Health..."}</span>
                  </p>
                  <p className="text-emerald-100 text-xs mt-1">Comparing 38+ plant pathology patterns</p>
                </div>
                {/* Animated scanline bar */}
                <div className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-emerald-400 to-transparent shadow-[0_0_15px_#34d399] z-10 animate-scanline" />
              </>
            )}

            {/* Quick Change Badge */}
            {!analyzing && (
              <button
                type="button"
                onClick={clearImage}
                className="absolute top-3 right-3 bg-black/60 hover:bg-black/80 backdrop-blur-md text-white text-xs font-semibold px-3 py-1.5 rounded-full transition-colors flex items-center gap-1.5"
              >
                <RefreshCw size={13} />
                <span>{t('retake_photo')}</span>
              </button>
            )}
          </div>
          
          {errorMsg && (
            <div className="bg-red-50 p-4 rounded-2xl text-center border border-red-200 animate-fadeIn">
              <p className="text-red-700 text-xs font-bold mb-2 flex items-center justify-center gap-1.5">
                <AlertTriangle size={15} />
                <span>{errorMsg}</span>
              </p>
              <button 
                onClick={() => setErrorMsg(null)}
                className="bg-red-100 text-red-800 px-4 py-1.5 rounded-xl text-xs font-bold hover:bg-red-200 transition-colors"
              >
                Dismiss
              </button>
            </div>
          )}

          {!errorMsg && (
            <div className="flex gap-3">
              <button 
                onClick={clearImage}
                disabled={analyzing}
                className="flex-1 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 py-3.5 rounded-2xl font-bold transition-colors text-sm disabled:opacity-50"
              >
                {t('retake_photo')}
              </button>
              <button 
                onClick={analyze}
                disabled={analyzing}
                className="flex-[2] bg-gradient-to-r from-emerald-600 to-green-700 hover:from-emerald-700 hover:to-green-800 text-white py-3.5 rounded-2xl font-bold flex items-center justify-center gap-2 shadow-md hover:scale-[1.01] active:scale-[0.99] transition-all text-sm disabled:opacity-50"
              >
                <Sparkles size={18} />
                <span>{analyzing ? (isTamil ? "பகுப்பாய்வு..." : "Analyzing...") : t('analyze_crop')}</span>
                {!analyzing && <ArrowRight size={17} />}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

