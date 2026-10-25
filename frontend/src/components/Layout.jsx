import { Outlet, NavLink, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Home, Leaf, Bot, CloudSun, Building, History, User, Languages } from 'lucide-react';
import NotificationCenter from './NotificationCenter';
import ErrorBoundary from './common/ErrorBoundary';

export default function Layout() {
  const { t, i18n } = useTranslation();
  const isTamil = i18n.language === 'ta';

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'ta' : 'en';
    i18n.changeLanguage(newLang);
    try {
      localStorage.setItem('agronex_language', newLang);
    } catch (e) {
      console.warn("Could not save language to localStorage:", e);
    }
  };

  const navItems = [
    { to: "/dashboard", label: t('home'), icon: Home },
    { to: "/crop", label: t('crop'), icon: Leaf, highlight: true },
    { to: "/weather", label: isTamil ? "வானிலை" : "Weather", icon: CloudSun },
    { to: "/assistant", label: t('ai'), icon: Bot },
    { to: "/schemes", label: isTamil ? "திட்டங்கள்" : "Schemes", icon: Building },
    { to: "/history", label: isTamil ? "வரலாறு" : "History", icon: History },
  ];

  return (
    <div className="flex flex-col min-h-screen bg-[#F8FAF9] text-[#16352A]">
      {/* Top Header (Desktop & Mobile) */}
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-gray-100/80 transition-all shadow-xs">
        <div className="flex justify-between items-center px-4 md:px-8 py-3 max-w-6xl mx-auto w-full">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center gap-2.5 group shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-600 to-green-700 flex items-center justify-center text-white shadow-sm shadow-emerald-700/20 group-hover:scale-105 transition-transform">
              <Leaf size={20} className="fill-current text-white/90" />
            </div>
            <div>
              <span className="text-lg sm:text-xl font-extrabold tracking-tight text-agronex-deep flex items-center gap-1.5 font-display">
                AgroNex
                <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.2 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200/50">
                  AI
                </span>
              </span>
              <p className="text-[9px] text-gray-400 font-medium hidden sm:block -mt-0.5">
                Autonomous Farming Copilot
              </p>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav className="hidden lg:flex items-center gap-1 bg-gray-50/80 p-1 rounded-2xl border border-gray-100">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                      isActive
                        ? 'bg-white text-emerald-800 shadow-2xs border border-gray-100 font-bold'
                        : 'text-gray-600 hover:text-emerald-800 hover:bg-white/60'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon size={15} className={isActive ? 'text-emerald-700' : 'text-gray-400'} />
                      <span>{item.label}</span>
                      {isActive && (
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>

          {/* Right Action: Notifications, Language Switcher & User Profile */}
          <div className="flex items-center gap-2">
            <NotificationCenter />

            <button 
              onClick={toggleLanguage}
              className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 bg-emerald-50/80 border border-emerald-200/60 text-emerald-900 rounded-full hover:bg-emerald-100 hover:scale-105 active:scale-95 transition-all shadow-2xs cursor-pointer"
              title="Change Language"
            >
              <Languages size={13} className="text-emerald-700" />
              <span>{i18n.language === 'en' ? 'தமிழ்' : 'English'}</span>
            </button>

            {(() => {
              const savedUser = localStorage.getItem('agronex_user');
              const userObj = savedUser ? JSON.parse(savedUser) : null;
              if (userObj) {
                return (
                  <div className="flex items-center gap-1.5">
                    <Link
                      to="/profile"
                      className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-full text-xs font-semibold text-gray-700 transition-colors"
                      title="Farmer Settings"
                    >
                      <User size={13} className="text-emerald-600" />
                      <span className="truncate max-w-[80px] hidden sm:inline">{userObj.name || 'Farmer'}</span>
                    </Link>
                  </div>
                );
              }
              return (
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1 text-xs font-bold px-3 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-full hover:shadow-xs transition-all"
                >
                  <User size={13} />
                  <span>{t('login')}</span>
                </Link>
              );
            })()}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-grow max-w-5xl mx-auto w-full px-4 sm:px-6 pt-5 pb-24 lg:pb-12">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>

      {/* Mobile Floating Bottom Navigation Dock */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-lg border-t border-gray-100 shadow-[0_-4px_24px_rgba(0,0,0,0.06)] px-2 py-1.5 flex justify-around items-center">
        {navItems.slice(0, 5).map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center py-1 px-2 rounded-2xl transition-all relative ${
                  isActive
                    ? 'text-emerald-800 font-bold scale-105'
                    : 'text-gray-400 hover:text-gray-600'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div
                    className={`w-9 h-6.5 rounded-full flex items-center justify-center transition-all ${
                      isActive ? 'bg-emerald-100 text-emerald-800 shadow-2xs' : ''
                    }`}
                  >
                    <Icon size={18} className={isActive ? 'text-emerald-800' : 'text-gray-500'} />
                  </div>
                  <span className={`text-[10px] mt-0.5 tracking-tight ${isActive ? 'font-bold text-emerald-800' : 'font-medium'}`}>
                    {item.label}
                  </span>
                </>
              )}
            </NavLink>
          );
        })}
        {/* Extra tab for Profile/History on mobile */}
        <NavLink
          to="/profile"
          className={({ isActive }) =>
            `flex flex-col items-center justify-center py-1 px-2 rounded-2xl transition-all relative ${
              isActive
                ? 'text-emerald-800 font-bold scale-105'
                : 'text-gray-400 hover:text-gray-600'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <div
                className={`w-9 h-6.5 rounded-full flex items-center justify-center transition-all ${
                  isActive ? 'bg-emerald-100 text-emerald-800 shadow-2xs' : ''
                }`}
              >
                <User size={18} className={isActive ? 'text-emerald-800' : 'text-gray-500'} />
              </div>
              <span className={`text-[10px] mt-0.5 tracking-tight ${isActive ? 'font-bold text-emerald-800' : 'font-medium'}`}>
                {isTamil ? 'அமைப்புகள்' : 'Profile'}
              </span>
            </>
          )}
        </NavLink>
      </nav>
    </div>
  );
}


