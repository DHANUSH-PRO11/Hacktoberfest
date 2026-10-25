import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ChevronLeft, MapPin, Search, CloudRain, Wind, ThermometerSun, AlertTriangle, CloudSun, Droplets } from 'lucide-react';
import { useLocation } from '../hooks/useLocation';
import { API_BASE_URL } from '../config/api';

export default function Weather() {
  const { i18n } = useTranslation();
  const { location, loading: locLoading, error: locError, requestLocation, updateLocationManually } = useLocation();
  const [weather, setWeather] = useState(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [searchMode, setSearchMode] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const isTamil = i18n.language === 'ta';

  const fetchWeather = useCallback(async (lat, lon) => {
    setWeatherLoading(true);
    try {
      const apiUrl = API_BASE_URL;
      const response = await fetch(`${apiUrl}/api/weather/forecast?lat=${lat}&lon=${lon}`);
      if (response.ok) {
        setWeather(await response.json());
      }
    } catch (err) {
      console.error(err);
    } finally {
      setWeatherLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!location?.latitude || !location?.longitude) return;
    const timer = setTimeout(() => {
      fetchWeather(location.latitude, location.longitude);
    }, 0);
    return () => clearTimeout(timer);
  }, [location?.latitude, location?.longitude, fetchWeather]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    try {
      const res = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(searchQuery)}&count=1&language=en&format=json`);
      const data = await res.json();
      if (data.results && data.results.length > 0) {
        const place = data.results[0];
        updateLocationManually(place.latitude, place.longitude, place.name, place.admin1, place.country);
        setSearchMode(false);
      } else {
        alert("Location not found");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const getAlertIcon = (type) => {
    switch (type) {
      case 'rain': return <CloudRain size={24} />;
      case 'thunderstorm': return <AlertTriangle size={24} />;
      case 'wind': return <Wind size={24} />;
      case 'heat': return <ThermometerSun size={24} />;
      case 'humidity': return <Droplets size={24} />;
      default: return <AlertTriangle size={24} />;
    }
  };

  const getAlertColors = (type) => {
    if (type === 'rain') return "bg-blue-50 border-blue-200 text-blue-900";
    if (type === 'wind') return "bg-orange-50 border-orange-200 text-orange-900";
    if (type === 'thunderstorm' || type === 'heat') return "bg-red-50 border-red-200 text-red-900";
    return "bg-green-50 border-green-200 text-green-900";
  };

  return (
    <div className="pb-16 max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link 
          to="/dashboard" 
          className="inline-flex items-center text-xs font-bold text-gray-500 hover:text-agronex-deep transition-colors bg-white px-3 py-1.5 rounded-full border border-gray-100 shadow-xs"
        >
          <ChevronLeft size={16} className="mr-0.5" />
          <span>{isTamil ? "முகப்பு" : "Dashboard"}</span>
        </Link>
        <h1 className="text-xl font-extrabold text-agronex-deep font-display">
          {isTamil ? "பண்ணை மணிநேர வானிலை முன்னறிவிப்பு" : "Hourly Farm Weather Forecast"}
        </h1>
        <div className="w-16"></div>
      </div>

      <div>
        {/* Location Section */}
        <div className="bg-white rounded-3xl p-5 shadow-xs border border-gray-100 mb-5">
          {!searchMode ? (
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
                  <MapPin size={20} />
                </div>
                <div>
                  <p className="text-[10px] font-extrabold text-gray-400 uppercase tracking-wider">
                    {isTamil ? "கண்காணிக்கப்படும் பண்ணை" : "MONITORED LOCATION"}
                  </p>
                  <h3 className="font-bold text-base text-agronex-deep">
                    {locLoading ? "Detecting location..." : location ? `${location.city}, ${location.state}` : "Unknown"}
                  </h3>
                  {weather?.location && (
                    <p className="text-[10px] text-gray-400 font-mono">
                      Lat: {Number(weather.location.latitude).toFixed(4)}, Lon: {Number(weather.location.longitude).toFixed(4)}
                    </p>
                  )}
                </div>
              </div>
              <button 
                onClick={() => setSearchMode(true)} 
                className="text-xs font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200/50 px-3.5 py-2 rounded-xl transition-all cursor-pointer"
              >
                {isTamil ? "மாற்று" : "Change City"}
              </button>
            </div>
          ) : (
            <form onSubmit={handleSearch} className="flex gap-2">
              <input 
                type="text" 
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder={isTamil ? "நகரத்தின் பெயரை தட்டச்சு செய்க..." : "Search Indian city or district..."} 
                className="flex-grow bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500"
                autoFocus
              />
              <button 
                type="submit" 
                className="bg-agronex-primary hover:bg-agronex-deep text-white px-4 rounded-xl font-bold flex items-center justify-center transition-colors"
              >
                <Search size={18} />
              </button>
              <button 
                type="button" 
                onClick={() => setSearchMode(false)} 
                className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 rounded-xl text-xs font-bold transition-colors"
              >
                {isTamil ? "ரத்து" : "Cancel"}
              </button>
            </form>
          )}

          {/* Quick Regional Agricultural District Presets */}
          <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider shrink-0 mr-1">
              {isTamil ? "முக்கிய பகுதிகள்:" : "Agri Hubs:"}
            </span>
            {[
              { name: "Coimbatore", ta: "கோயம்புத்தூர்", lat: 11.0168, lon: 76.9558 },
              { name: "Thanjavur", ta: "தஞ்சாவூர்", lat: 10.7870, lon: 79.1378 },
              { name: "Madurai", ta: "மதுரை", lat: 9.9252, lon: 78.1198 },
              { name: "Salem", ta: "சேலம்", lat: 11.6643, lon: 78.1460 },
              { name: "Trichy", ta: "திருச்சி", lat: 10.7905, lon: 78.7047 }
            ].map((dist) => (
              <button
                key={dist.name}
                type="button"
                onClick={() => updateLocationManually(dist.lat, dist.lon, dist.name, "Tamil Nadu", "India")}
                className="px-2.5 py-1 bg-gray-50 hover:bg-emerald-50 hover:text-emerald-800 text-gray-600 rounded-lg font-medium whitespace-nowrap border border-gray-200/60 transition-all text-[11px] cursor-pointer"
              >
                {isTamil ? dist.ta : dist.name}
              </button>
            ))}
          </div>
        </div>

        {locError && (
          <div className="bg-amber-50 p-4 rounded-2xl border border-amber-200 flex items-center justify-between mb-5 text-xs text-amber-800">
            <span>{locError}</span>
            <button
              onClick={requestLocation}
              className="bg-amber-100 hover:bg-amber-200 text-amber-900 px-3 py-1.5 rounded-xl font-bold transition-colors cursor-pointer"
            >
              {isTamil ? "மீண்டும் முயற்சி" : "Retry GPS"}
            </button>
          </div>
        )}

        {weatherLoading ? (
          <div className="text-center py-12 bg-white rounded-3xl border border-gray-100 shadow-xs">
            <div className="w-10 h-10 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin mx-auto mb-3"></div>
            <p className="font-semibold text-gray-600 text-sm">
              {isTamil ? "வானிலை முன்னறிவிப்பு பெறப்படுகிறது..." : "Fetching numerical weather forecast..."}
            </p>
          </div>
        ) : weather && weather.current ? (
          <div className="space-y-6">
            {/* Forecast Stale Warning Banner if applicable */}
            {weather.warning && (
              <div className="bg-amber-50 border border-amber-200 p-3.5 rounded-2xl flex items-center justify-between text-xs text-amber-900">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={16} className="text-amber-600 shrink-0" />
                  <span>{weather.warning}</span>
                </div>
                <span className="font-mono text-[10px] bg-amber-100 px-2 py-0.5 rounded text-amber-800 shrink-0">STALE CACHE</span>
              </div>
            )}

            {/* Current Weather Summary Card */}
            <div className="bg-gradient-to-br from-[#0B5D3B] via-[#0f7249] to-[#16A36A] rounded-3xl p-6 sm:p-8 text-white shadow-lg relative overflow-hidden">
              <div className="relative z-10 flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-white/15 text-emerald-100 inline-block border border-white/20">
                      Open-Meteo Numerical Forecast
                    </span>
                    <span className="text-[10px] text-emerald-200">
                      7-day horizon • 24h Hourly
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <p className="text-5xl sm:text-6xl font-black font-display tracking-tight">
                      {Math.round(weather.current.temperature)}°
                    </p>
                    <span className="text-xl font-semibold opacity-70">C</span>
                  </div>
                  <p className="text-xl font-bold mt-1 text-emerald-100 font-display">
                    {isTamil && weather.condition_ta ? weather.condition_ta : weather.condition_en}
                  </p>
                </div>

                <div className="text-right">
                  <div className="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur-md flex items-center justify-center text-white ml-auto mb-2 border border-white/20">
                    <CloudSun size={32} />
                  </div>
                  <p className="text-xs font-medium text-emerald-100">
                    Feels like {Math.round(weather.current.apparent_temperature || (weather.current.temperature + 2))}°C
                  </p>
                  <p className="text-[10px] text-emerald-200 mt-1 font-mono">
                    {weather.cache_status === 'fresh' && weather.is_cached ? `Cached (${Math.round(weather.cache_age_seconds)}s)` : 'Live Fetch'}
                  </p>
                </div>
              </div>
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-white/15 relative z-10 text-xs">
                <div className="bg-black/15 backdrop-blur-xs p-2.5 rounded-xl border border-white/10">
                  <span className="opacity-70 text-[10px] uppercase font-bold block mb-0.5">Humidity</span>
                  <div className="flex items-center gap-1.5 font-bold text-sm">
                    <Droplets size={14} className="text-blue-300" />
                    <span>{weather.current.humidity}%</span>
                  </div>
                </div>

                <div className="bg-black/15 backdrop-blur-xs p-2.5 rounded-xl border border-white/10">
                  <span className="opacity-70 text-[10px] uppercase font-bold block mb-0.5">Wind Speed</span>
                  <div className="flex items-center gap-1.5 font-bold text-sm">
                    <Wind size={14} className="text-teal-300" />
                    <span>{weather.current.wind_speed} km/h</span>
                  </div>
                </div>

                <div className="bg-black/15 backdrop-blur-xs p-2.5 rounded-xl border border-white/10">
                  <span className="opacity-70 text-[10px] uppercase font-bold block mb-0.5">Precipitation</span>
                  <div className="flex items-center gap-1.5 font-bold text-sm">
                    <CloudRain size={14} className="text-cyan-300" />
                    <span>{weather.current.precipitation || 0} mm</span>
                  </div>
                </div>

                <div className="bg-black/15 backdrop-blur-xs p-2.5 rounded-xl border border-white/10">
                  <span className="opacity-70 text-[10px] uppercase font-bold block mb-0.5">Retrieved</span>
                  <div className="font-semibold text-[11px] text-emerald-100 truncate">
                    {new Date(weather.last_updated).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>

              {/* Attribution and Grounding Notice */}
              <div className="mt-3 pt-2 border-t border-white/10 text-[10px] text-emerald-200/90 leading-tight">
                {weather.data_accuracy_notice || "Forecast values are derived from numerical weather prediction models and are not measurements from an on-field physical sensor station."}
              </div>
              
              <CloudSun size={200} className="absolute -bottom-16 -right-16 opacity-10 pointer-events-none text-white" />
            </div>

            {/* Configured Agricultural Spray-Condition Advisory Engine (Section 5) */}
            {(() => {
              const spray = weather.spray_advisory || {};
              const level = spray.advisory_level || "FAVORABLE_WINDOW";
              const isHighRisk = level === "HIGH_RISK";
              const isCaution = level === "CAUTION";

              let badgeColor = "bg-emerald-50 border-emerald-200 text-emerald-900";
              let badgeTitle = isTamil ? "தெளிப்புக்கு சாதகமான வானிலை இடைவெளி" : "Weather Window May Be Favorable for Spraying";
              if (isHighRisk) {
                badgeColor = "bg-red-50 border-red-200 text-red-900";
                badgeTitle = isTamil ? "தெளிக்க வேண்டாம் — அதிக அபாயம்" : "Weather Conditions Unfavorable — High Wash-off Risk";
              } else if (isCaution) {
                badgeColor = "bg-amber-50 border-amber-200 text-amber-900";
                badgeTitle = isTamil ? "எச்சரிக்கையுடன் செயல்படவும் — காற்று அபாயம்" : "Spray Caution Advised — Wind Drift Risk";
              }

              const explanation = (isTamil && spray.explanation_ta) ? spray.explanation_ta : (spray.explanation || "");
              const actuals = spray.actual_forecast_values || {};
              const thresholds = spray.threshold_values || { rain_probability_pct: 60, precipitation_mm: 2.0, wind_speed_kmh: 25.0 };

              return (
                <div className={`p-5 rounded-3xl border ${badgeColor} space-y-3 shadow-2xs`}>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-white/80 border border-current">
                      {isTamil ? "வேளாண் தெளிப்பு பாதுகாப்பு வழிகாட்டி" : "Agricultural Spray-Condition Advisory (Section 5)"}
                    </span>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-white/70">
                      Level: {level}
                    </span>
                  </div>

                  <div>
                    <h4 className="font-extrabold text-base">{badgeTitle}</h4>
                    <p className="text-xs leading-relaxed opacity-95 mt-1">{explanation}</p>
                  </div>

                  {/* Triggered Rules List if any */}
                  {spray.triggered_rules && spray.triggered_rules.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] uppercase font-bold tracking-wider opacity-75">
                        {isTamil ? "தூண்டப்பட்ட எச்சரிக்கை விதிகள்:" : "Triggered Warning Triggers:"}
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {spray.triggered_rules.map((rule, idx) => (
                          <span key={idx} className="bg-white/85 text-red-900 border border-red-200 text-[11px] font-semibold px-2 py-0.5 rounded-md">
                            ⚠️ {rule}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actual Values vs Configurable Caution Thresholds */}
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-black/5 text-[11px]">
                    <div className="bg-white/70 p-2 rounded-xl">
                      <span className="block text-[10px] opacity-70">Wind Speed</span>
                      <strong className="text-xs">{actuals.wind_speed_kmh ?? "--"} km/h</strong>
                      <span className="block text-[9px] text-gray-500">Max: {thresholds.wind_speed_kmh} km/h</span>
                    </div>
                    <div className="bg-white/70 p-2 rounded-xl">
                      <span className="block text-[10px] opacity-70">Rain Probability</span>
                      <strong className="text-xs">{actuals.rain_probability_pct ?? "--"}%</strong>
                      <span className="block text-[9px] text-gray-500">Max: {thresholds.rain_probability_pct}%</span>
                    </div>
                    <div className="bg-white/70 p-2 rounded-xl">
                      <span className="block text-[10px] opacity-70">Precipitation</span>
                      <strong className="text-xs">{actuals.precipitation_mm ?? "--"} mm</strong>
                      <span className="block text-[9px] text-gray-500">Max: {thresholds.precipitation_mm} mm</span>
                    </div>
                  </div>

                  {/* Mandatory Agronomic Safety Limitations Notice */}
                  <div className="pt-2 border-t border-black/5 text-[11px] opacity-80 leading-relaxed">
                    <strong>{isTamil ? "முக்கிய வேளாண் கட்டுப்பாடு:" : "Agronomic Safety Limitations:"} </strong>
                    {spray.limitations || (isTamil
                      ? "வானிலை சாதகமாக இருப்பது மட்டுமே தெளிப்பை பாதுகாப்பானதாக்காது. பூச்சிக்கொல்லி லேபிள் வழிகாட்டுதல், பயிர் வளர்ச்சி பருவம், பாதுகாப்பு இடைவெளிகளை கட்டாயம் பின்பற்றவும்."
                      : "Favorable forecast conditions alone do not certify chemical spraying is universally safe. Applicators must consult pesticide product labels, crop growth stage, mandatory buffer zones, and local agricultural advice.")}
                  </div>
                </div>
              );
            })()}

            {/* Today Hourly Forecast */}
            {weather.hourly && weather.hourly.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-extrabold text-base text-agronex-deep font-display">
                    {isTamil ? "இன்றைய மணிநேர வானிலை முன்னறிவிப்பு" : "Hourly Weather Forecast"}
                  </h3>
                  <span className="text-[11px] text-gray-500 font-medium">
                    Units: °C • % • km/h
                  </span>
                </div>
                <div className="bg-white rounded-3xl border border-gray-100 shadow-xs overflow-hidden divide-y divide-gray-100">
                  {[weather.hourly[0], weather.hourly[3], weather.hourly[6], weather.hourly[9], weather.hourly[12], weather.hourly[15]].filter(Boolean).map((hourData, idx) => {
                    const timeObj = new Date(hourData.time);
                    const timeStr = timeObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    return (
                      <div key={idx} className="flex items-center justify-between p-3.5 px-5 hover:bg-gray-50/60 transition-colors">
                        <span className="w-16 font-bold text-xs text-gray-700">{timeStr}</span>
                        <div className="flex items-center gap-1.5 text-blue-600 font-semibold text-xs">
                          <CloudRain size={15} />
                          <span>{hourData.precipitation_probability}% {isTamil ? "மழை" : "Rain"}</span>
                        </div>
                        {hourData.wind_speed !== undefined && hourData.wind_speed !== null && (
                          <div className="hidden sm:flex items-center gap-1 text-teal-700 font-medium text-xs">
                            <Wind size={13} />
                            <span>{hourData.wind_speed} km/h</span>
                          </div>
                        )}
                        <div className="w-16 text-right font-extrabold text-sm text-agronex-deep">
                          {Math.round(hourData.temperature)}°C
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Agricultural Weather Alerts */}
            <div>
              <h3 className="font-extrabold text-base text-agronex-deep mb-3 flex items-center gap-2 font-display">
                <AlertTriangle size={18} className="text-amber-500" />
                <span>{isTamil ? "வேளாண் வானிலை எச்சரிக்கைகள்" : "Farming Weather Advisories"}</span>
              </h3>
              
              <div className="space-y-3">
                {weather.alerts && weather.alerts.length > 0 ? (
                  weather.alerts.map((alert, idx) => (
                    <div key={idx} className={`p-4 rounded-2xl border ${getAlertColors(alert.type)} flex items-start gap-3.5 shadow-xs`}>
                      <div className="mt-1 text-emerald-700">{getAlertIcon(alert.type)}</div>
                      <div>
                        <h4 className="font-bold text-sm mb-0.5">{isTamil ? alert.title_ta : alert.title_en}</h4>
                        <p className="text-xs font-medium opacity-90 leading-relaxed mb-2">
                          {isTamil ? alert.message_ta : alert.message_en}
                        </p>
                        {alert.probability && (
                          <span className="inline-block bg-white/60 px-2 py-0.5 rounded-md text-[11px] font-bold">
                            {alert.probability}% Probability
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="bg-emerald-50/70 p-4 rounded-2xl border border-emerald-100 flex items-center gap-3 shadow-xs">
                    <div className="bg-emerald-100 p-2 rounded-xl text-emerald-700">
                      <CloudSun size={20} />
                    </div>
                    <div>
                      <h4 className="font-bold text-emerald-900 text-xs">
                        {isTamil ? "தற்போது குறிப்பிடத்தக்க வானிலை எச்சரிக்கைகள் இல்லை." : "✓ Normal weather conditions for crops."}
                      </h4>
                      <p className="text-[11px] text-emerald-700 font-medium">
                        {isTamil ? "பயிர்களுக்கு உகந்த வானிலை நிலவுகிறது." : "Forecast indicates favorable conditions for farming operations."}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* 7 Day Forecast */}
            <div>
              <h3 className="font-extrabold text-base text-agronex-deep mb-3 font-display">
                {isTamil ? "அடுத்த 7 நாட்கள் முன்னறிவிப்பு" : "7-Day Regional Forecast"}
              </h3>
              <div className="bg-white rounded-3xl border border-gray-100 shadow-xs overflow-hidden divide-y divide-gray-100">
                {weather.forecast?.map((day, idx) => {
                  const dateObj = new Date(day.date);
                  const dayName = idx === 0 ? (isTamil ? 'இன்று' : 'Today') : dateObj.toLocaleDateString('en-US', { weekday: 'short' });
                  return (
                    <div key={idx} className="flex items-center justify-between p-3.5 px-5 hover:bg-gray-50/60 transition-colors">
                      <span className="w-18 font-bold text-xs text-gray-700">{dayName}</span>
                      <div className="flex items-center gap-1.5 text-blue-600 font-semibold text-xs">
                        <CloudRain size={14} />
                        <span>{day.precipitation_probability_mean}%</span>
                      </div>
                      <div className="w-24 text-right font-extrabold text-xs text-gray-800">
                        {Math.round(day.temperature_max)}° <span className="text-gray-400 font-medium ml-1">{Math.round(day.temperature_min)}°</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : weather && !weather.success ? (
          <div className="bg-red-50 p-6 rounded-3xl border border-red-100 text-center space-y-3">
            <AlertTriangle className="text-red-400 mx-auto mb-1" size={32} />
            <h3 className="text-red-800 font-bold text-base">
              {isTamil ? "வானிலை முன்னறிவிப்புத் தரவைப் பெற முடியவில்லை" : "Weather Forecast Service Unavailable"}
            </h3>
            <p className="text-red-600 text-xs font-medium max-w-md mx-auto">
              {weather.error || (isTamil ? "தற்காலிக சேவையகப் பிழை. மாதிரித் தரவுகள் போலியாக உருவாக்கப்படாது." : "Open-Meteo forecast service temporarily unavailable. No fake data is fabricated.")}
            </p>
            <button
              onClick={() => location && fetchWeather(location.latitude, location.longitude)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-red-100 hover:bg-red-200 text-red-800 rounded-xl text-xs font-bold transition-colors cursor-pointer"
            >
              <span>{isTamil ? "மீண்டும் முயற்சி" : "Retry Connection"}</span>
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
