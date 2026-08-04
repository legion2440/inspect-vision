const IMAGE_EXTENSIONS = new Map([
  ['image/jpeg', 'jpg'],
  ['image/jpg', 'jpg'],
  ['image/png', 'png'],
]);

/** Resolve the supported image extension encoded by a data URL or URL path. */
export function imageExtension(imageUrl) {
  const value = String(imageUrl || '').trim();
  const dataMime = /^data:([^;,]+)/i.exec(value)?.[1]?.toLowerCase();
  if (dataMime && IMAGE_EXTENSIONS.has(dataMime)) return IMAGE_EXTENSIONS.get(dataMime);

  try {
    const pathname = new URL(value, 'http://inspect-vision.local').pathname.toLowerCase();
    if (pathname.endsWith('.jpeg') || pathname.endsWith('.jpg')) return 'jpg';
    if (pathname.endsWith('.png')) return 'png';
  } catch (_error) {
    /* Invalid URLs fall through to an extension-free filename. */
  }
  return '';
}

/** Build a safe annotated-image filename without claiming an unknown media type. */
export function annotatedImageFilename(inspectionId, imageUrl) {
  const stem = String(inspectionId || 'inspection')
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, '_') || 'inspection';
  const extension = imageExtension(imageUrl);
  return extension ? `${stem}.${extension}` : stem;
}
