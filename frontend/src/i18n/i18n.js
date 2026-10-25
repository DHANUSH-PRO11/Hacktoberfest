import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enTranslation from './en.json';
import taTranslation from './ta.json';

const savedLanguage = typeof window !== 'undefined' ? localStorage.getItem('agronex_language') : null;

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: enTranslation },
      ta: { translation: taTranslation }
    },
    lng: savedLanguage || 'en', // persisted or default language
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false // react already safes from xss
    }
  });

export default i18n;
