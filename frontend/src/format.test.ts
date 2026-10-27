import { describe, expect, it } from 'vitest';
import { changeDirection, dateLabel, foldDiacritics, formatMoneyInput, money, monthLabel, parseMoneyInput, percent, points, volatilityLabel } from './format';

describe('PortfolioVN formatters', () => {
  it('formats VND as whole đồng using the active locale', () => {
    expect(money(1234567, 'vi')).toBe('1.234.567 ₫');
    expect(money(1234567, 'en')).toBe('VND 1,234,567');
  });

  it('formats returns as decimal fractions and preserves signed direction', () => {
    expect(percent(0.0941, 'vi')).toBe('9,41%');
    expect(percent(-0.0563, 'en')).toBe('−5.63%');
    expect(percent(0.0234, 'en', 2, true)).toBe('+2.34%');
    expect(percent(0, 'vi', 2, true)).toBe('0,00%');
  });

  it('formats percentage-point deviations separately from returns', () => {
    expect(points(2.25, 'vi')).toBe('+2,25 điểm %');
    expect(points(-0.5, 'en')).toBe('−0.50 pp');
  });

  it('uses inclusive volatility band boundaries from the research rules', () => {
    expect(volatilityLabel(0.0799, 'vi')).toBe('Thấp');
    expect(volatilityLabel(0.08, 'vi')).toBe('Trung bình');
    expect(volatilityLabel(0.1299, 'en')).toBe('Medium');
    expect(volatilityLabel(0.13, 'en')).toBe('High');
  });

  it('does not color tiny movements as gains or losses', () => {
    expect(changeDirection(0.01, 'vi')).toEqual({ label: 'Tăng', className: 'up' });
    expect(changeDirection(-0.01, 'en')).toEqual({ label: 'Down', className: 'down' });
    expect(changeDirection(1e-13, 'vi')).toEqual({ label: 'Đi ngang', className: 'flat' });
    expect(changeDirection(null, 'en')).toEqual({ label: 'Flat', className: 'flat' });
  });

  it('renders DD/MM/YYYY for the Vietnamese locale and keeps the HCMC calendar day', () => {
    expect(dateLabel('2026-08-17', 'vi')).toBe('17/08/2026');
    expect(dateLabel('2026-08-17', 'en')).toBe('08/17/2026');
  });

  it('parses pasted thousands separators by locale and rejects decimal or mixed input', () => {
    expect(parseMoneyInput('100.000.000 ₫', 'vi')).toBe(100_000_000);
    expect(parseMoneyInput('VND 100,000,000', 'en')).toBe(100_000_000);
    expect(parseMoneyInput('1 000 000', 'vi')).toBe(1_000_000);
    expect(parseMoneyInput('1,000', 'vi')).toBeNull();
    expect(parseMoneyInput('1,000.5', 'en')).toBeNull();
    expect(formatMoneyInput('1000000', 'vi')).toBe('1.000.000');
  });

  it('formats research months without shifting the Vietnam calendar month', () => {
    expect(monthLabel('2026-08', 'vi')).toBe('08/2026');
    expect(monthLabel('2026-08', 'en')).toBe('Aug 2026');
  });

  it('folds Vietnamese diacritics, including đ, for search', () => {
    expect(foldDiacritics('Tăng trưởng — Bất động sản')).toBe('tang truong — bat dong san');
  });
});
