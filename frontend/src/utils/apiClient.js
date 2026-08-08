import * as mock from '../mocks/mockApi.js';
import { appendModelId, appendProductName } from './models.js';

const BASE = String(import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/$/, '');
const USE_MOCK = String(import.meta.env.VITE_USE_MOCK ?? 'false').trim().toLowerCase() === 'true';

async function unwrap(res) {
  if (!res.ok) {
    let message = 'Request failed (' + res.status + ')';
    try {
      const body = await res.json();
      message = body.detail || body.message || message;
    } catch (err) {
      /* non-JSON error body — keep the status message */
    }
    throw new Error(message);
  }
  return res.json();
}

async function unwrapBlob(res) {
  if (!res.ok) {
    let message = 'Request failed (' + res.status + ')';
    try {
      const body = await res.json();
      message = body.detail || body.message || message;
    } catch (err) {
      /* non-JSON error body — keep the status message */
    }
    throw new Error(message);
  }
  return res.blob();
}

export async function inspectImage(file, { signal, modelId, productName } = {}) {
  if (USE_MOCK) return mock.inspectImage(file, { modelId, productName });
  const form = new FormData();
  form.append('image', file, file.name);
  appendModelId(form, modelId);
  appendProductName(form, productName);
  return unwrap(await fetch(BASE + '/api/inspect', { method: 'POST', body: form, signal }));
}

export async function inspectFrame(blob, { signal, modelId, productName } = {}) {
  if (USE_MOCK) return mock.inspectFrame({ modelId, productName });
  const form = new FormData();
  form.append('frame', blob, 'frame.jpg');
  appendModelId(form, modelId);
  appendProductName(form, productName);
  return unwrap(await fetch(BASE + '/api/stream', { method: 'POST', body: form, signal }));
}

export async function getModels({ signal } = {}) {
  if (USE_MOCK) return mock.getModels();
  return unwrap(await fetch(BASE + '/api/models', { signal }));
}

export async function getSamples({ signal } = {}) {
  if (USE_MOCK) return mock.getSamples();
  return unwrap(await fetch(BASE + '/api/samples', { signal }));
}

export function sampleImageUrl(sample) {
  const path = sample?.imageUrl || '';
  if (USE_MOCK || /^(?:data:|blob:|https?:)/i.test(path)) return path;
  return BASE + path;
}

export async function getSampleImage(sample, { signal } = {}) {
  const response = await fetch(sampleImageUrl(sample), { signal });
  return unwrapBlob(response);
}

export async function getHistory(filters = {}, { signal } = {}) {
  if (USE_MOCK) return mock.getHistory(filters);
  const qs = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v !== '' && v != null && v !== 'all'),
  ).toString();
  return unwrap(await fetch(BASE + '/api/history' + (qs ? '?' + qs : ''), { signal }));
}

export async function getInspection(id) {
  if (USE_MOCK) return mock.getInspection(id);
  return unwrap(await fetch(BASE + '/api/history/' + encodeURIComponent(id)));
}

export async function deleteInspection(id) {
  if (USE_MOCK) return mock.deleteInspection(id);
  return unwrap(await fetch(BASE + '/api/history/' + encodeURIComponent(id), { method: 'DELETE' }));
}

export async function clearHistory() {
  if (USE_MOCK) return mock.clearHistory();
  return unwrap(await fetch(BASE + '/api/history/clear', { method: 'POST' }));
}

export function exportUrl(filters = {}) {
  const qs = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v !== '' && v != null && v !== 'all'),
  ).toString();
  return BASE + '/api/export' + (qs ? '?' + qs : '');
}

export async function exportHistory(filters = {}, { signal } = {}) {
  if (USE_MOCK) throw new Error('Server CSV export is unavailable in mock mode');
  return unwrapBlob(await fetch(exportUrl(filters), { signal }));
}

export const usingMock = USE_MOCK;
