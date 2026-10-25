import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const isTamil = typeof window !== 'undefined' && localStorage.getItem('agronex_language') === 'ta';

      return (
        <div className="min-h-[50vh] flex items-center justify-center p-6">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-md w-full text-center border border-red-100 shadow-md space-y-4">
            <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto">
              <AlertTriangle size={28} />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-gray-900 font-display">
                {isTamil ? "பக்கத்தில் எதிர்பாராத பிழை ஏற்பட்டது" : "Something Went Wrong"}
              </h2>
              <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                {isTamil 
                  ? "பக்கத்தை ஏற்றுவதில் சிக்கல் ஏற்பட்டுள்ளது. மீண்டும் முயற்சிக்கவும் அல்லது முகப்புக்குச் செல்லவும்."
                  : "An unexpected error occurred while rendering this page. Please try refreshing or return to the dashboard."}
              </p>
            </div>

            <div className="flex gap-2.5 justify-center pt-2">
              <button
                onClick={this.handleReload}
                className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold transition-colors inline-flex items-center gap-1.5 cursor-pointer"
              >
                <RefreshCw size={14} />
                <span>{isTamil ? "மீண்டும் முயற்சி" : "Try Again"}</span>
              </button>
              <a
                href="/dashboard"
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-xs font-bold transition-colors inline-flex items-center gap-1.5"
              >
                <Home size={14} />
                <span>{isTamil ? "முகப்பு" : "Dashboard"}</span>
              </a>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
