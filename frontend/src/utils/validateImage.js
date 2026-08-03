const MAX_BYTES = Number(import.meta.env.VITE_MAX_UPLOAD_BYTES || 10485760);
const ACCEPTED = (import.meta.env.VITE_ACCEPTED_TYPES || 'image/jpeg,image/png').split(',');

/** Mirrors the backend guards so the operator gets the error before the upload. */
export function validateImage(file) {
  if (!file) return 'No file selected';
  if (!ACCEPTED.includes(file.type)) return 'Unsupported file type';
  if (file.size > MAX_BYTES) return 'File size exceeds 10MB limit';
  return null;
}

export const acceptAttr = ACCEPTED.join(',');
