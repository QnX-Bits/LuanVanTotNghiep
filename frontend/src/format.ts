import type { Locale } from './types';

const localeName = (locale: Locale) => locale === 'vi' ? 'vi-VN' : 'en-US';
export function money(value: number, locale: Locale, withCurrency = true): string {
  const formatted = new Intl.NumberFormat(localeName(locale), { maximumFractionDigits: 0 }).format(Math.round(value));
  return withCurrency ? (locale === 'vi' ? `${formatted} ₫` : `VND ${formatted}`) : formatted;
}
export function parseMoneyInput(value: string, locale: Locale): number | null {
  const cleaned = value.trim().replace(/(?:VND|₫)/gi, '').trim().replace(/[\s\u00a0\u202f'’]/g, '');
  if (/^\d+$/.test(cleaned)) return Number(cleaned);
  const separator = locale === 'vi' ? '\\.' : ',';
  if (new RegExp(`^\\d{1,3}(?:${separator}\\d{3})+$`).test(cleaned)) return Number(cleaned.replace(/[.,]/g, ''));
  return null;
}
export function formatMoneyInput(value: string, locale: Locale): string {
  const amount = parseMoneyInput(value, locale);
  return amount === null ? value : new Intl.NumberFormat(localeName(locale), { maximumFractionDigits: 0 }).format(amount);
}
export function percent(value: number | null | undefined, locale: Locale, digits = 2, signed = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const valueText = new Intl.NumberFormat(localeName(locale), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Math.abs(value * 100));
  const sign = signed ? value > 0 ? '+' : value < 0 ? '−' : '' : value < 0 ? '−' : '';
  return `${sign}${valueText}%`;
}
export function points(value: number | null | undefined, locale: Locale, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const n = new Intl.NumberFormat(localeName(locale), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Math.abs(value));
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${n} ${locale === 'vi' ? 'điểm %' : 'pp'}`;
}
export function number(value: number | null | undefined, locale: Locale, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat(localeName(locale), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}
export function dateLabel(value: string, locale: Locale): string {
  const d = new Date(`${value}T00:00:00+07:00`);
  return new Intl.DateTimeFormat(localeName(locale), { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Asia/Ho_Chi_Minh' }).format(d);
}
export function monthLabel(value: string, locale: Locale): string {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return value || '—';
  if (locale === 'vi') return `${match[2]}/${match[1]}`;
  const monthDate = new Date(`${match[1]}-${match[2]}-01T12:00:00Z`);
  return new Intl.DateTimeFormat(localeName(locale), { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(monthDate);
}
export function volatilityLabel(value: number, locale: Locale): string {
  if (value < 0.08) return locale === 'vi' ? 'Thấp' : 'Low';
  if (value < 0.13) return locale === 'vi' ? 'Trung bình' : 'Medium';
  return locale === 'vi' ? 'Cao' : 'High';
}
export function changeDirection(value: number | null, locale: Locale): { label: string; className: 'up' | 'down' | 'flat' } {
  if (value === null || Math.abs(value) < 1e-12) return { label: locale === 'vi' ? 'Đi ngang' : 'Flat', className: 'flat' };
  return value > 0 ? { label: locale === 'vi' ? 'Tăng' : 'Up', className: 'up' } : { label: locale === 'vi' ? 'Giảm' : 'Down', className: 'down' };
}
export function foldDiacritics(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
}
