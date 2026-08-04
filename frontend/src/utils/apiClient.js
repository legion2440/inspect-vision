import * as mock from '../mocks/mockApi.js';
import { appendModelId } from './models.js';

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

/** POST /api/inspect — multipart image upload, returns the inspection record. */
export async function inspectImage(file, { signal, modelId } = {}) {
  if (USE_MOCK) return mock.inspectImage(file, { modelId });
  const form = new FormData();
  form.append('image', file, file.name);
  appendModelId(form, modelId);
  return unwrap(await fetch(BASE + '/api/inspect', { method: 'POST', body: form, signal }));
}

/** POST /api/stream — one webcam frame, returns detections for that frame. */
export async function inspectFrame(blob, { signal, modelId } = {}) {
  if (USE_MOCK) return mock.inspectFrame({ modelId });
  const form = new FormData();
  form.append('frame', blob, 'frame.jpg');
  appendModelId(form, modelId);
  return unwrap(await fetch(BASE + '/api/stream', { method: 'POST', body: form, signal }));
}

/** GET /api/models — registry projection for upload/live selection. */
export async function getModels({ signal } = {}) {
  if (USE_MOCK) return mock.getModels();
  return unwrap(await fetch(BASE + '/api/models', { signal }));
}

/** GET /api/samples — curated metadata only; image bytes use the image endpoint. */
export async function getSamples({ signal } = {}) {
  if (USE_MOCK) return mock.getSamples();
  return unwrap(await fetch(BASE + '/api/samples', { signal }));
}

export function sampleImageUrl(sample) {
  const path = sample?.imageUrl || '';
  if (USE_MOCK || /^(?:data:|blob:|https?:)/i.test(path)) return path;
  return BASE + path;
}

/** GET /api/samples/{id}/image — original redistributable sample bytes. */
export async function getSampleImage(sample, { signal } = {}) {
  const response = await fetch(sampleImageUrl(sample), { signal });
  return unwrapBlob(response);
}

/** GET /api/history?from=&to=&type=&q= */
export async function getHistory(filters = {}, { signal } = {}) {
  if (USE_MOCK) return mock.getHistory(filters);
  const qs = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v !== '' && v != null && v !== 'all'),
  ).toString();
  return unwrap(await fetch(BASE + '/api/history' + (qs ? '?' + qs : ''), { signal }));
}

/** GET /api/history/{id} */
export async function getInspection(id) {
  if (USE_MOCK) return mock.getInspection(id);
  return unwrap(await fetch(BASE + '/api/history/' + encodeURIComponent(id)));
}

/** DELETE /api/history/{id} */
export async function deleteInspection(id) {
  if (USE_MOCK) return mock.deleteInspection(id);
  return unwrap(await fetch(BASE + '/api/history/' + encodeURIComponent(id), { method: 'DELETE' }));
}

/** POST /api/history/clear */
export async function clearHistory() {
  if (USE_MOCK) return mock.clearHistory();
  return unwrap(await fetch(BASE + '/api/history/clear', { method: 'POST' }));
}

/** GET /api/export — CSV download URL (client-side fallback lives in utils/csv.js). */
export function exportUrl(filters = {}) {
  const qs = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v !== '' && v != null && v !== 'all'),
  ).toString();
  return BASE + '/api/export' + (qs ? '?' + qs : '');
}

/** GET /api/export — return the server-generated CSV body. */
export async function exportHistory(filters = {}, { signal } = {}) {
  if (USE_MOCK) throw new Error('Server CSV export is unavailable in mock mode');
  return unwrapBlob(await fetch(exportUrl(filters), { signal }));
}

export const usingMock = USE_MOCK;
