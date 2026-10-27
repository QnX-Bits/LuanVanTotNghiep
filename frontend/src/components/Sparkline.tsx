import { useMemo } from 'react';
export function Sparkline({ values, positive = true, width = 112, height = 32, label }: { values: (number | null)[]; positive?: boolean; width?: number; height?: number; label?: string }) {
  const points = useMemo(() => {
    const data = values.map((v) => v === null ? NaN : Number(v));
    const finite = data.filter(Number.isFinite);
    if (!finite.length) return '';
    const min = Math.min(...finite); const max = Math.max(...finite); const range = max - min || 1;
    let path = ''; let active = false;
    data.forEach((value, index) => {
      if (!Number.isFinite(value)) { active = false; return; }
      const x = data.length <= 1 ? width / 2 : (index / (data.length - 1)) * width;
      const y = height - 3 - ((value - min) / range) * (height - 7);
      path += `${active ? ' L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`; active = true;
    });
    return path;
  }, [values, height, width]);
  const id = `spark-${positive ? 'u' : 'd'}-${label?.replace(/\W/g, '') || 'series'}`;
  return <svg className={`sparkline ${positive ? 'spark-up' : 'spark-down'}`} width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label || 'Monthly trend'}>
    <title>{label || 'Monthly trend'}</title><path d={points} fill="none" stroke={`url(#${id})`} strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinecap="square" strokeLinejoin="miter" />
    <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={positive ? '#176d49' : '#8b2f2f'} stopOpacity="1" /><stop offset="1" stopColor={positive ? '#176d49' : '#8b2f2f'} stopOpacity=".42" /></linearGradient></defs>
  </svg>;
}
