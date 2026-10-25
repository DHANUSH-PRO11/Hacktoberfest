import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Search, ExternalLink, ShieldCheck, CheckCircle2, FileText, Users, Building, AlertCircle, RefreshCw } from 'lucide-react';
import { API_BASE_URL } from '../config/api';

export default function Schemes() {
  const { i18n } = useTranslation();
  const isTamil = i18n.language === 'ta';
  const [schemes, setSchemes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');

  const categories = [
    { id: 'ALL', labelEn: 'All Schemes', labelTa: 'அனைத்து திட்டங்கள்' },
    { id: 'Income Support', labelEn: 'Income Support', labelTa: 'வருமான உதவி' },
    { id: 'Crop Insurance', labelEn: 'Crop Insurance', labelTa: 'பயிர் காப்பீடு' },
    { id: 'Irrigation & Water Conservation', labelEn: 'Irrigation', labelTa: 'பாசனம்' },
    { id: 'Subsidized Institutional Credit', labelEn: 'Credit & Loans', labelTa: 'பயிர் கடன்' },
    { id: 'State Integrated Development', labelEn: 'State Schemes', labelTa: 'மாநில திட்டங்கள்' }
  ];

  const fetchSchemes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/schemes?lang=${isTamil ? 'ta' : 'en'}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSchemes(data);
    } catch (err) {
      setError(err.message || 'Failed to load government schemes');
    } finally {
      setLoading(false);
    }
  }, [isTamil]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchSchemes();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchSchemes]);

  const filteredSchemes = schemes.filter((s) => {
    const matchesCat = selectedCategory === 'ALL' || s.category === selectedCategory;
    const q = searchQuery.toLowerCase().trim();
    if (!q) return matchesCat;
    const matchesQuery = 
      (s.name && s.name.toLowerCase().includes(q)) ||
      (s.name_ta && s.name_ta.toLowerCase().includes(q)) ||
      (s.benefits && s.benefits.toLowerCase().includes(q)) ||
      (s.benefits_ta && s.benefits_ta.toLowerCase().includes(q)) ||
      (s.category && s.category.toLowerCase().includes(q));
    return matchesCat && matchesQuery;
  });

  return (
    <div className="space-y-6 pb-8">
      {/* Header Banner */}
      <div className="bg-gradient-to-br from-[#081c15] via-[#1b4332] to-[#2d6a4f] rounded-3xl p-6 sm:p-8 text-white shadow-md relative overflow-hidden">
        <div className="absolute -right-8 -bottom-8 w-48 h-48 bg-emerald-400/10 rounded-full blur-2xl pointer-events-none" />
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md text-emerald-200 text-xs font-semibold mb-3 border border-white/20">
            <Building size={13} className="text-emerald-300" />
            <span>{isTamil ? 'மத்திய & தமிழக அரசு திட்டங்கள்' : 'Central & State Government Programs'}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight font-display mb-2">
            {isTamil ? 'விவசாயிகளுக்கான அரசு திட்டங்கள் & மானியங்கள்' : 'Agricultural Subsidies & Schemes'}
          </h1>
          <p className="text-emerald-100/90 text-sm leading-relaxed">
            {isTamil
              ? 'விவசாய உற்பத்தியை பெருக்க மத்திய மற்றும் தமிழக அரசு வழங்கும் நேரடி நிதி உதவி, பாசன மானியங்கள், குறைந்த வட்டி பயிர்க்கடன் மற்றும் பயிர் காப்பீட்டுத் திட்டங்களின் முழுமையான வழிகாட்டி.'
              : 'Verified directory of income support, crop insurance, drip irrigation subsidies, and concessional institutional credit for Indian farmers.'}
          </p>
        </div>
      </div>

      {/* Official Government Verification Advisory */}
      <div className="bg-emerald-50/80 border border-emerald-200/80 rounded-2xl p-4 flex items-start gap-3 text-xs text-emerald-900">
        <ShieldCheck size={18} className="text-emerald-700 shrink-0 mt-0.5" />
        <div>
          <p className="font-bold mb-0.5">
            {isTamil ? 'அதிகாரப்பூர்வ தகவல்கள் சரிபார்ப்பு' : 'Verified Official Government Sources'}
          </p>
          <p className="text-emerald-800/90 leading-relaxed">
            {isTamil
              ? 'அனைத்து திட்ட விபரங்களும் pmkisan.gov.in, pmfby.gov.in, myscheme.gov.in ஆகிய தளங்களின்படி தொகுக்கப்பட்டுள்ளன. தகுதி மற்றும் விண்ணப்ப செயல்முறைகளை அதிகாரப்பூர்வ போர்டல் அல்லது உங்கள் வட்டார வேளாண்மை உதவி இயக்குநர் அலுவலகத்தில் உறுதிப்படுத்தவும்.'
              : 'Details curated directly from official ministries (pmkisan.gov.in, pmfby.gov.in, myscheme.gov.in). Exact eligibility and deadlines are subject to local district administration verification.'}
          </p>
        </div>
      </div>

      {/* Search & Filter Controls */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={isTamil ? 'திட்டம் அல்லது பயனை தேடவும்...' : 'Search by scheme name, benefits, or keywords...'}
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 shadow-2xs"
            />
          </div>
          <button
            onClick={fetchSchemes}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 font-semibold rounded-xl text-sm transition-all shadow-2xs"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin text-emerald-600' : 'text-gray-500'} />
            <span>{isTamil ? 'புதுப்பி' : 'Refresh'}</span>
          </button>
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all cursor-pointer ${
                selectedCategory === cat.id
                  ? 'bg-emerald-700 text-white shadow-xs'
                  : 'bg-white hover:bg-gray-100 text-gray-600 border border-gray-200/70'
              }`}
            >
              {isTamil ? cat.labelTa : cat.labelEn}
            </button>
          ))}
        </div>
      </div>

      {/* Content State: Loading, Error, or List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white p-5 rounded-2xl border border-gray-100 animate-pulse space-y-3">
              <div className="h-5 bg-gray-200 rounded-md w-3/4"></div>
              <div className="h-4 bg-gray-100 rounded-md w-1/3"></div>
              <div className="h-16 bg-gray-50 rounded-xl"></div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center space-y-3">
          <AlertCircle size={32} className="text-red-500 mx-auto" />
          <h3 className="font-bold text-red-900">{isTamil ? 'திட்டங்களை ஏற்றுவதில் பிழை' : 'Failed to Load Schemes'}</h3>
          <p className="text-xs text-red-700">{error}</p>
          <button
            onClick={fetchSchemes}
            className="px-4 py-2 bg-red-600 text-white rounded-xl text-xs font-bold hover:bg-red-700"
          >
            {isTamil ? 'மீண்டும் முயற்சிக்கவும்' : 'Retry'}
          </button>
        </div>
      ) : filteredSchemes.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center space-y-2">
          <Building size={36} className="text-gray-300 mx-auto" />
          <h3 className="font-bold text-gray-700 text-sm">
            {isTamil ? 'எந்தவொரு திட்டமும் பொருந்தவில்லை' : 'No matching schemes found'}
          </h3>
          <p className="text-xs text-gray-400">
            {isTamil ? 'வேறு வார்த்தைகளை தேடிப் பார்க்கவும்' : 'Try adjusting your search query or category filter.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredSchemes.map((scheme) => (
            <div
              key={scheme.id}
              className="bg-white rounded-2xl border border-gray-200/80 p-5 shadow-2xs hover:shadow-md hover:border-emerald-300 transition-all flex flex-col justify-between space-y-4 group"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-200/60">
                    {scheme.category}
                  </span>
                  <span className="text-[11px] font-semibold text-gray-400">#{scheme.id}</span>
                </div>

                <h3 className="text-base font-extrabold text-gray-900 group-hover:text-emerald-800 transition-colors leading-snug">
                  {isTamil && scheme.name_ta ? scheme.name_ta : scheme.name}
                </h3>
                {isTamil && scheme.name_ta && (
                  <p className="text-xs text-gray-500 font-medium mt-0.5">{scheme.name}</p>
                )}

                {/* Key Benefits */}
                <div className="mt-3 bg-[#F8FAF9] p-3.5 rounded-xl border border-gray-100">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-900 mb-1">
                    <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
                    <span>{isTamil ? 'முக்கிய நன்மைகள் & மானியம்:' : 'Key Benefits & Subsidy:'}</span>
                  </div>
                  <p className="text-xs text-gray-700 leading-relaxed font-medium">
                    {isTamil && scheme.benefits_ta ? scheme.benefits_ta : scheme.benefits}
                  </p>
                </div>

                {/* Eligibility & Target Audience */}
                <div className="mt-3 space-y-2 text-xs">
                  <div className="flex items-start gap-2 text-gray-600">
                    <Users size={14} className="text-gray-400 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-gray-800">{isTamil ? 'தகுதி:' : 'Eligibility:'} </strong>
                      <span>{isTamil && scheme.who_can_apply_ta ? scheme.who_can_apply_ta : scheme.who_can_apply}</span>
                    </div>
                  </div>
                  <div className="flex items-start gap-2 text-gray-600">
                    <FileText size={14} className="text-gray-400 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-gray-800">{isTamil ? 'தேவையான ஆவணங்கள்:' : 'Required Documents:'} </strong>
                      <span>{isTamil && scheme.required_documents_ta ? scheme.required_documents_ta : (scheme.required_documents || scheme.eligibility)}</span>
                    </div>
                  </div>

                  {(scheme.application_steps || scheme.application_steps_ta) && (
                    <div className="bg-emerald-50/50 p-2.5 rounded-xl border border-emerald-100/70 text-[11px] text-emerald-900">
                      <strong className="block mb-0.5 text-emerald-950 font-bold">
                        {isTamil ? 'விண்ணப்பிக்கும் முறை:' : 'Application Steps:'}
                      </strong>
                      <p className="leading-relaxed">
                        {isTamil && scheme.application_steps_ta ? scheme.application_steps_ta : scheme.application_steps}
                      </p>
                    </div>
                  )}
                </div>

                {scheme.last_verified && (
                  <div className="mt-2 text-[10px] text-gray-400 flex items-center justify-between">
                    <span>{isTamil ? `சரிபார்க்கப்பட்டது: ${scheme.last_verified}` : `Verified: ${scheme.last_verified}`}</span>
                  </div>
                )}
              </div>

              {/* Action Button: Verified Portal Link */}
              <div className="pt-2 border-t border-gray-100 flex items-center justify-between">
                <span className="text-[11px] text-gray-400 flex items-center gap-1">
                  <ShieldCheck size={13} className="text-emerald-600" />
                  <span>{isTamil ? 'அரசு தளம்' : 'Official Portal'}</span>
                </span>
                <a
                  href={scheme.source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white rounded-xl text-xs font-bold transition-all shadow-2xs group/btn"
                >
                  <span>{isTamil ? 'விண்ணப்பிக்க / விபரம்' : 'Apply / Learn More'}</span>
                  <ExternalLink size={13} className="group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5 transition-transform" />
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Statutory Disclaimer Footer */}
      <div className="bg-gray-50 border border-gray-200 rounded-2xl p-4 text-[11px] text-gray-500 leading-relaxed">
        <strong>{isTamil ? "சட்டரீதியான அறிவிப்பு: " : "Statutory Agricultural Program Notice: "}</strong>
        {isTamil
          ? "அக்ரோநெக்ஸ் AI விவசாயிகளுக்கு மத்திய மற்றும் மாநில அரசு நலத்திட்டங்கள் குறித்த பொது விழிப்புணர்வு தகவல்களை மட்டுமே வழங்குகிறது. இத்தளம் அரசு திட்ட தகுதிக்கோ, மானிய ஒப்புதலுக்கோ அல்லது நிதி விடுவிப்புக்கோ எந்தவித உத்தரவாதமும் அளிக்காது. விண்ணப்பங்களின் இறுதி ஏற்பு அரசு துறை அதிகாரிகளின் நேரடி ஆவண சரிபார்ப்புக்கு உட்பட்டது."
          : "AgroNex AI provides informational access to officially announced public agricultural programs. AgroNex does not process government benefits or guarantee subsidy approval. Sanction and disbursement remain under the sole jurisdiction of designated government ministries and field inspection authorities."}
      </div>
    </div>
  );
}
