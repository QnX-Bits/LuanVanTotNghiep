import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { resources } from './resources';

const saved = typeof window !== 'undefined' ? window.localStorage.getItem('pvn-locale') : null;
void i18n.use(initReactI18next).init({
  resources,
  lng: saved === 'en' ? 'en' : 'vi',
  fallbackLng: 'vi',
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
