import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { 
  Camera, Upload, Bot, CloudSun, Sparkles, ArrowRight, 
  Activity, History, Building, Calendar, MessageSquare 
} from 'lucide-react';
import LocationWeatherCard from '../components/LocationWeatherCard';
import { API_BASE_URL } from '../config/api';

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const [currentHour] = useState(() => new Date().getHours());
  const isTamil = i18n.language === 'ta';

  const [recentAnalyses, setRecentAnalyses] = useState([]);
  const [recentChats, setRecentChats] = useState([]);
  const [featuredSchemes, setFeaturedSchemes] = useState([]);
  const [cropStats, setCropStats] = useState({ total_scans: 0, healthy_count: 0, condition_alerts: 0, inconclusive_count: 0 });
  const [loadingData, setLoadingData] = useState(true);

  const [dashQuery, setDashQuery] = useState("");
  const [dashLoading, setDashLoading] = useState(false);
  const [dashReply, setDashReply] = useState(null);

  const handleDashAsk = async (queryText) => {
    const q = queryText || dashQuery;
    if (!q || !q.trim()) return;
    setDashLoading(true);
    setDashReply(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: q,
          language: i18n.language || 'en'
        })
      });
      if (res.ok) {
        const data = await res.json();
        setDashReply({ query: q, answer: data.reply });
        setDashQuery("");
      }
    } catch (err) {
      console.warn("Dashboard chat error:", err);
    } finally {
      setDashLoading(false);
    }
  };

  const getTimeGreeting = () => {
    if (currentHour < 12) return isTamil ? "இனிய காலை வணக்கம்" : "Good Morning";
    if (currentHour < 17) return isTamil ? "இனிய மதிய வணக்கம்" : "Good Afternoon";
    return isTamil ? "இனிய மாலை வணக்கம்" : "Good Evening";
  };


  useEffect(() => {
    const loadDashboardData = async () => {
      setLoadingData(true);
      try {
        // 1. Fetch real crop history & stats
        const [cropsRes, statsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/crops/history`),
          fetch(`${API_BASE_URL}/api/crops/stats`)
        ]);

        if (cropsRes.ok) {
          const cropsData = await cropsRes.json();
          setRecentAnalyses(cropsData.slice(0, 3));
        }
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setCropStats(statsData);
        }
      } catch (e) {
        console.warn('Dashboard crops fetch:', e);
      }

      try {
        // 2. Fetch real assistant chat history
        const chatRes = await fetch(`${API_BASE_URL}/api/assistant/history?limit=4`);
        if (chatRes.ok) {
          const chatData = await chatRes.json();
          setRecentChats(chatData.slice(0, 4));
        }
      } catch (e) {
        console.warn('Dashboard chats fetch:', e);
      }

      try {
        // 3. Fetch schemes preview
        const schRes = await fetch(`${API_BASE_URL}/api/schemes?lang=${isTamil ? 'ta' : 'en'}`);
        if (schRes.ok) {
          const schData = await schRes.json();
          setFeaturedSchemes(schData.slice(0, 2));
        }
      } catch (e) {
        console.warn('Dashboard schemes fetch:', e);
      } finally {
        setLoadingData(false);
      }
    };

    loadDashboardData();
  }, [isTamil]);

  // Compute summary metrics from real database statistics
  const totalScans = cropStats.total_scans;
  const healthyCount = cropStats.healthy_count;
  const diseasedCount = cropStats.condition_alerts;
  const inconclusiveCount = cropStats.inconclusive_count;

  return (
    <div className="space-y-6 pb-8">
      {/* Header Greeting Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-800">
              {isTamil ? "அக்ரோநெக்ஸ் ஸ்மார்ட் பண்ணை" : "AgroNex Smart Farm"}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-agronex-deep font-display mt-0.5">
            {getTimeGreeting()}, {isTamil ? "விவசாயி" : "Farmer"}!
          </h1>
        </div>

        {/* Live System Status Pill */}
        <div className="flex items-center gap-2 bg-white px-3.5 py-1.5 rounded-full border border-gray-100 shadow-2xs self-start sm:self-auto">
          <Activity size={14} className="text-emerald-600" />
          <span className="text-xs font-semibold text-gray-600">
            Gemma 4 Copilot: <strong className="text-emerald-700 font-bold">Active</strong>
          </span>
        </div>
      </div>

      {/* Crop Health Overview KPI Metrics from SQLite Database */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-2xs">
          <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
            {isTamil ? "மொத்த ஆய்வுகள்" : "Total Analyses"}
          </span>
          <div className="text-2xl font-black text-agronex-deep mt-1 font-mono">
            {totalScans}
          </div>
          <span className="text-[10px] text-emerald-700 font-semibold">
            {isTamil ? "உண்மையான தரவுத்தளம்" : "Live Database Records"}
          </span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-2xs">
          <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
            {isTamil ? "ஆரோக்கிய பயிர்" : "Healthy Leaves"}
          </span>
          <div className="text-2xl font-black text-emerald-600 mt-1 font-mono">
            {healthyCount}
          </div>
          <span className="text-[10px] text-gray-500 font-medium">
            {totalScans > 0 ? `${Math.round((healthyCount / totalScans) * 100)}% vigor rate` : (isTamil ? "ஆய்வு செய்யப்படவில்லை" : "No scans logged")}
          </span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-2xs">
          <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
            {isTamil ? "கண்டறிந்த நோய்கள்" : "Condition Alerts"}
          </span>
          <div className="text-2xl font-black text-amber-600 mt-1 font-mono">
            {diseasedCount}
          </div>
          <span className="text-[10px] text-amber-700 font-medium">
            {diseasedCount > 0 ? (isTamil ? "கண்காணிப்பு தேவை" : "Requires monitoring") : (isTamil ? "அறிகுறிகள் இல்லை" : "Clean foliage")}
          </span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-gray-100 shadow-2xs">
          <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
            {isTamil ? "நிச்சயமற்றவை" : "Inconclusive"}
          </span>
          <div className="text-2xl font-black text-blue-600 mt-1 font-mono">
            {inconclusiveCount}
          </div>
          <span className="text-[10px] text-blue-700 font-semibold">
            {isTamil ? "மறுபடம் / KVK உதவி" : "Retake / KVK recommended"}
          </span>
        </div>
      </div>

      {/* Main Hero Diagnostic Card */}
      <div className="relative rounded-3xl overflow-hidden shadow-lg bg-gradient-to-br from-[#081c15] via-[#1b4332] to-[#2d6a4f] p-6 sm:p-8 text-white">

        <div className="absolute -right-10 -bottom-10 w-60 h-60 bg-white/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -top-12 right-20 w-44 h-44 bg-emerald-400/20 rounded-full blur-2xl pointer-events-none" />

        <div className="relative z-10 max-w-xl">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/15 backdrop-blur-md text-emerald-100 text-xs font-semibold mb-3 border border-white/20">
            <Sparkles size={13} className="text-emerald-300" />
            <span>{isTamil ? "உடனடி AI நோய் கண்டறிதல்" : "Instant AI Crop Diagnosis"}</span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-black font-display tracking-tight leading-tight mb-2">
            {isTamil ? "பயிர் இலையை ஸ்கேன் செய்து நோயைக் கண்டறியவும்" : "Detect Crop Disease with AI"}
          </h2>
          <p className="text-emerald-100/90 text-xs sm:text-sm leading-relaxed mb-6 font-medium">
            {isTamil 
              ? "பாதிக்கப்பட்ட பயிர் இலையின் புகைப்படத்தை எடுத்து உடனடி தீர்வு மற்றும் உர ஆலோசனையைப் பெறுங்கள்." 
              : "Snap a photo of the affected plant leaf to receive immediate disease diagnosis, spray safety rules & treatment guidelines."}
          </p>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <Link 
              to="/crop" 
              className="bg-white hover:bg-emerald-50 text-emerald-950 font-bold px-6 py-3.5 rounded-2xl flex items-center justify-center gap-2 shadow-md hover:scale-[1.02] active:scale-[0.98] transition-all text-xs sm:text-sm group"
            >
              <Camera size={19} className="text-emerald-700" />
              <span>{isTamil ? "புகைப்படம் எடுக்கவும்" : "Take Leaf Photo"}</span>
              <ArrowRight size={16} className="text-emerald-600 group-hover:translate-x-1 transition-transform" />
            </Link>

            <Link 
              to="/crop" 
              className="bg-white/15 hover:bg-white/25 backdrop-blur-md border border-white/25 text-white font-semibold px-5 py-3.5 rounded-2xl flex items-center justify-center gap-2 transition-all text-xs sm:text-sm"
            >
              <Upload size={18} />
              <span>{isTamil ? "கேலரியிலிருந்து பதிவேற்று" : "Upload Image"}</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Quick Action Highlights */}
      <div>
        <div className="flex items-center justify-between mb-3 px-1">
          <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
            {isTamil ? "முக்கிய சேவைகள்" : "Essential Tools"}
          </h3>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          {[
            { 
              icon: <Camera size={20} />, 
              title: t('crop'), 
              desc: isTamil ? "நோய் ஸ்கேன்" : "Health Scan", 
              to: "/crop", 
              iconBg: "bg-emerald-100 text-emerald-800",
              border: "hover:border-emerald-300"
            },
            { 
              icon: <Bot size={20} />, 
              title: t('ai'), 
              desc: isTamil ? "குரல் உதவியாளர்" : "Sarvam AI Voice", 
              to: "/assistant", 
              iconBg: "bg-blue-100 text-blue-800",
              badge: "Voice",
              border: "hover:border-blue-300"
            },
            { 
              icon: <CloudSun size={20} />, 
              title: isTamil ? "வானிலை" : "Weather", 
              desc: isTamil ? "மழை & காற்று" : "Rain & Wind", 
              to: "/weather", 
              iconBg: "bg-amber-100 text-amber-800",
              border: "hover:border-amber-300"
            },
            { 
              icon: <Building size={20} />, 
              title: isTamil ? "அரசு திட்டங்கள்" : "Govt Schemes", 
              desc: isTamil ? "மானியங்கள்" : "Subsidies & Credit", 
              to: "/schemes", 
              iconBg: "bg-purple-100 text-purple-800",
              border: "hover:border-purple-300"
            },
          ].map((item, idx) => (
            <Link 
              key={idx} 
              to={item.to} 
              className={`bg-white p-4 rounded-2xl border border-gray-100 shadow-2xs hover:shadow-md transition-all flex flex-col justify-between group relative overflow-hidden ${item.border}`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110 ${item.iconBg}`}>
                  {item.icon}
                </div>
                {item.badge && (
                  <span className="text-[10px] font-extrabold px-1.5 py-0.2 rounded-md bg-blue-50 text-blue-700 border border-blue-200/60 uppercase">
                    {item.badge}
                  </span>
                )}
              </div>
              <div>
                <h4 className="font-bold text-gray-900 text-xs sm:text-sm group-hover:text-emerald-700 transition-colors">
                  {item.title}
                </h4>
                <p className="text-[11px] text-gray-500 font-medium">
                  {item.desc}
                </p>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Live Location Weather Card with Spray Alert Engine */}
      <LocationWeatherCard />

      {/* Two Column Layout: Recent Crop Analyses & Recent AI Conversations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Recent Diagnoses */}
        <div className="bg-white rounded-3xl border border-gray-200/80 p-5 shadow-2xs space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <History size={18} className="text-emerald-700" />
                <h3 className="text-sm font-extrabold text-gray-900 font-display">
                  {isTamil ? 'சமீபத்திய பயிர் சோதனைகள்' : 'Recent Plant Diagnoses'}
                </h3>
              </div>
              <Link
                to="/history"
                className="text-xs font-bold text-emerald-700 hover:text-emerald-800 flex items-center gap-1"
              >
                <span>{isTamil ? 'அனைத்தும்' : 'View all'}</span>
                <ArrowRight size={12} />
              </Link>
            </div>

            {loadingData ? (
              <div className="space-y-2">
                {[1, 2].map((i) => (
                  <div key={i} className="h-14 bg-gray-50 rounded-xl animate-pulse"></div>
                ))}
              </div>
            ) : recentAnalyses.length === 0 ? (
              <div className="p-6 text-center text-xs text-gray-400 bg-gray-50/50 rounded-2xl">
                <p>{isTamil ? 'இன்னும் பரிசோதனைகள் இல்லை.' : 'No recent inspections recorded yet.'}</p>
                <Link to="/crop" className="mt-2 inline-block text-emerald-700 font-bold underline">
                  {isTamil ? 'இலையை ஸ்கேன் செய்க' : 'Scan a leaf now'}
                </Link>
              </div>
            ) : (
              <div className="space-y-2.5">
                {recentAnalyses.map((item, idx) => {
                  const isHealthy = item.is_healthy || (item.condition && item.condition.toLowerCase().includes('healthy'));
                  const conf = Math.round((item.confidence || 0) * (item.confidence <= 1 ? 100 : 1));
                  const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString(isTamil ? 'ta-IN' : 'en-US', {
                    month: 'short',
                    day: 'numeric'
                  }) : 'Recent';

                  return (
                    <div
                      key={idx}
                      className="p-3 rounded-2xl bg-gray-50/60 border border-gray-100 flex items-center justify-between gap-3 hover:bg-emerald-50/30 transition-colors"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-extrabold text-gray-900 truncate">{item.crop}</span>
                          <span className="text-[10px] text-gray-400 flex items-center gap-1">
                            <Calendar size={11} /> {dateStr}
                          </span>
                        </div>
                        <p className="text-xs text-gray-600 font-medium truncate mt-0.5">{item.condition}</p>
                      </div>

                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${
                          isHealthy
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {conf}%
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Quick Stat Footer */}
          {totalScans > 0 && (
            <div className="pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500 font-medium">
              <span>{isTamil ? 'மொத்தம்:' : 'History:'} {totalScans}</span>
              <span className="text-emerald-700 font-bold">
                {healthyCount} {isTamil ? 'ஆரோக்கியம்' : 'Healthy'}
              </span>
              <span className="text-amber-700 font-bold">
                {diseasedCount} {isTamil ? 'பாதிப்பு' : 'At Risk'}
              </span>
            </div>
          )}
        </div>

        {/* Recent Copilot Conversations */}
        <div className="bg-white rounded-3xl border border-gray-200/80 p-5 shadow-2xs space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <MessageSquare size={18} className="text-blue-700" />
                <h3 className="text-sm font-extrabold text-gray-900 font-display">
                  {isTamil ? 'சமீபத்திய உரையாடல்கள்' : 'Recent Assistant Consultations'}
                </h3>
              </div>
              <Link
                to="/assistant"
                className="text-xs font-bold text-blue-700 hover:text-blue-800 flex items-center gap-1"
              >
                <span>{isTamil ? 'கேளுங்கள்' : 'Open Copilot'}</span>
                <ArrowRight size={12} />
              </Link>
            </div>

            {loadingData ? (
              <div className="space-y-2">
                {[1, 2].map((i) => (
                  <div key={i} className="h-14 bg-gray-50 rounded-xl animate-pulse"></div>
                ))}
              </div>
            ) : recentChats.length === 0 ? (
              <div className="p-6 text-center text-xs text-gray-400 bg-gray-50/50 rounded-2xl">
                <p>{isTamil ? 'உரையாடல் பதிவுகள் இல்லை.' : 'No recent assistant questions recorded.'}</p>
                <Link to="/assistant" className="mt-2 inline-block text-blue-700 font-bold underline">
                  {isTamil ? 'உதவியாளரிடம் கேளுங்கள்' : 'Ask a farming question'}
                </Link>
              </div>
            ) : (
              <div className="space-y-2.5">
                {recentChats.slice(0, 3).map((chat, idx) => (
                  <div
                    key={chat.id || idx}
                    className="p-3 rounded-2xl bg-gray-50/60 border border-gray-100 flex items-start gap-2.5 hover:bg-blue-50/30 transition-colors"
                  >
                    <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-black flex items-center justify-center shrink-0 mt-0.5">
                      {chat.role === 'user' ? '👨‍🌾' : '🤖'}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-gray-800 font-semibold line-clamp-1">{chat.message}</p>
                      <span className="text-[10px] text-gray-400">
                        {chat.role === 'user' ? (isTamil ? 'விவசாயி கேள்வி' : 'Farmer Query') : (isTamil ? 'AI ஆலோசனை' : 'AgroNex Advice')}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Link
            to="/assistant"
            className="pt-2 text-xs font-bold text-blue-700 hover:text-blue-800 flex items-center gap-1"
          >
            <span>{isTamil ? 'புதிய குரல் அல்லது உரை ஆலோசனை தொடங்க' : 'Ask a new voice or text question'}</span>
            <ArrowRight size={13} />
          </Link>
        </div>
      </div>

      {/* Interactive Quick AI Chat Interface with Example Questions */}
      <div className="bg-white rounded-3xl border border-gray-200/80 p-5 sm:p-6 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-gray-100 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-600 to-green-700 text-white flex items-center justify-center shadow-xs">
              <Bot size={18} />
            </div>
            <div>
              <h3 className="text-sm font-extrabold text-agronex-deep font-display">
                {isTamil ? "அக்ரோநெக்ஸ் AI நேரடி விவசாய வழிகாட்டி" : "AgroNex AI Quick Farmer Assistant"}
              </h3>
              <p className="text-[11px] text-gray-400">
                {isTamil ? "Gemma 4 அடிப்படையிலான விவசாய வினா-விடை மற்றும் வானிலை பாதுகாப்பு" : "Powered by Gemma 4 with weather risk intelligence & safe farming rules"}
              </p>
            </div>
          </div>
          <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full font-mono self-start sm:self-auto">
            Bilingual AI Copilot
          </span>
        </div>

        {/* Clickable Example Questions */}
        <div className="space-y-1.5">
          <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider block">
            {isTamil ? "மாதிரி கேள்விகள் (உடனடி பதிலுக்கு கிளிக் செய்க):" : "Example Questions (Click to Ask):"}
          </span>
          <div className="flex flex-wrap gap-2">
            {[
              {
                en: "Should I spray pesticide today given tomorrow's rainfall forecast?",
                ta: "நாளைய மழை முன்னறிவிப்பில் இன்று மருந்து தெளிக்கலாமா?"
              },
              {
                en: "What are organic bio-control remedies for tomato early blight?",
                ta: "தக்காளி இலைக்கருகல் நோய்க்கு இயற்கை தீர்வுகள் என்ன?"
              },
              {
                en: "How to prevent fungal disease spread during high humidity (>80%)?",
                ta: "அதிக ஈரப்பதம் இருக்கும்போது பூஞ்சை பரவுவதை தடுப்பது எப்படி?"
              }
            ].map((ex, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleDashAsk(isTamil ? ex.ta : ex.en)}
                disabled={dashLoading}
                className="text-xs px-3 py-1.5 bg-gray-50 hover:bg-emerald-50 text-emerald-900 border border-gray-200/80 hover:border-emerald-300 rounded-full font-medium transition-all text-left disabled:opacity-50"
              >
                💬 {isTamil ? ex.ta : ex.en}
              </button>
            ))}
          </div>
        </div>

        {/* Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleDashAsk();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={dashQuery}
            onChange={(e) => setDashQuery(e.target.value)}
            placeholder={isTamil ? "பயிர் நோய், உரம் அல்லது தெளிப்பு பற்றி கேளுங்கள்..." : "Ask about crop diseases, organic treatments, or spray timing..."}
            className="flex-1 bg-gray-50 border border-gray-200 rounded-2xl px-4 py-2.5 text-xs text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
          />
          <button
            type="submit"
            disabled={dashLoading || !dashQuery.trim()}
            className="bg-agronex-primary hover:bg-agronex-deep text-white text-xs font-bold px-5 py-2.5 rounded-2xl flex items-center gap-1.5 shadow-xs transition-all disabled:opacity-50"
          >
            <span>{dashLoading ? (isTamil ? "பகுப்பாய்வு..." : "Thinking...") : (isTamil ? "கேளுங்கள்" : "Ask AI")}</span>
            <ArrowRight size={14} />
          </button>
        </form>

        {/* Direct Response Display */}
        {dashReply && (
          <div className="p-4 rounded-2xl bg-gradient-to-br from-emerald-50/80 to-teal-50/40 border border-emerald-200/80 space-y-2 animate-in fade-in duration-300">
            <div className="flex items-center justify-between text-[11px] text-gray-500">
              <span className="font-bold text-emerald-800">Q: "{dashReply.query}"</span>
              <span className="text-[10px] bg-white px-2 py-0.5 rounded border border-emerald-100 font-mono">Gemma 4</span>
            </div>
            <p className="text-xs text-gray-800 leading-relaxed font-normal whitespace-pre-line">
              {dashReply.answer}
            </p>
          </div>
        )}
      </div>

      {/* Featured Government Subsidies Preview */}

      {featuredSchemes.length > 0 && (
        <div className="bg-gradient-to-br from-emerald-50/80 to-teal-50/50 rounded-3xl border border-emerald-200/70 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Building size={18} className="text-emerald-800" />
              <h3 className="text-sm font-extrabold text-emerald-950 font-display">
                {isTamil ? 'பயனுள்ள அரசு மானியங்கள் & திட்டங்கள்' : 'Featured Government Schemes & Subsidies'}
              </h3>
            </div>
            <Link
              to="/schemes"
              className="text-xs font-bold text-emerald-800 hover:text-emerald-900 flex items-center gap-1"
            >
              <span>{isTamil ? 'அனைத்து திட்டங்கள்' : 'Explore all'}</span>
              <ArrowRight size={12} />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {featuredSchemes.map((s) => (
              <div
                key={s.id}
                className="bg-white/80 backdrop-blur-xs p-3.5 rounded-2xl border border-emerald-100 flex flex-col justify-between space-y-2"
              >
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100/70 px-2 py-0.5 rounded-full inline-block mb-1">
                    {s.category}
                  </span>
                  <h4 className="text-xs font-bold text-gray-900 line-clamp-1">
                    {isTamil && s.name_ta ? s.name_ta : s.name}
                  </h4>
                  <p className="text-[11px] text-gray-600 line-clamp-2 mt-1 leading-relaxed">
                    {isTamil && s.benefits_ta ? s.benefits_ta : s.benefits}
                  </p>
                </div>
                <Link
                  to="/schemes"
                  className="text-[11px] font-bold text-emerald-700 hover:text-emerald-800 flex items-center gap-1 pt-1"
                >
                  <span>{isTamil ? 'விபரம் பார்க்க' : 'View eligibility & portal'}</span>
                  <ArrowRight size={11} />
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
