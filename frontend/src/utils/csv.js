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
  downloadBlob(blob, filename);
}

export function downloadBlob(blob, filename = 'inspection-history.csv') {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
