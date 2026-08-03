import { defectTypes } from './format.js';

const cell = (v) => {
  const s = String(v ?? '');
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
};

export function toCsv(records = []) {
  const head = ['inspectionId', 'timestamp', 'defectCount', 'types', 'qualityScore', 'status'];
  const rows = records.map((r) => [
    r.inspectionId,
    r.timestamp,
    r.totalDefects ?? (r.defects || []).length,
    defectTypes(r).join(' | '),
    r.qualityScore ?? '',
    r.status,
  ]);
  return [head, ...rows].map((row) => row.map(cell).join(',')).join('\n');
}

export function downloadCsv(records, filename = 'inspection-history.csv') {
  const blob = new Blob([toCsv(records)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
