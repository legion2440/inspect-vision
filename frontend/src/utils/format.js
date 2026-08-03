export const pct = (c) => Math.round((c ?? 0) * 100) + '%';

export const stamp = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(0, 10) + ' ' + d.toISOString().slice(11, 19);
};

export const dayOf = (iso) => (iso ? String(iso).slice(0, 10) : '');

export const boxLabel = (b) => [b.x, b.y, b.width, b.height].join(', ');

export const defectTypes = (rec) => [...new Set((rec.defects || []).map((d) => d.type))];
