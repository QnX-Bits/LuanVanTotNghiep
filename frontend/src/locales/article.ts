import type { Locale } from '../types';
export function articleText(value: string | Record<Locale, string> | undefined, locale: Locale): string {
  if (!value) return '';
  if (typeof value === 'string') return value;
  return value[locale] || value.vi || value.en || '';
}
