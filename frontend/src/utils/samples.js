export function groupSamplesByDomain(samples = []) {
  return samples.reduce((groups, sample) => {
    const key = sample.domain || 'Other';
    const current = groups.get(key) || [];
    current.push(sample);
    groups.set(key, current);
    return groups;
  }, new Map());
}

export function recommendedModelFor(sample, models = []) {
  return models.find((model) => model.id === sample?.recommendedModelId) || null;
}

function throwIfAborted(signal) {
  if (!signal?.aborted) return;
  if (signal.reason) throw signal.reason;
  const error = new Error('Sample inspection cancelled');
  error.name = 'AbortError';
  throw error;
}

export async function inspectShowcaseSample({
  sample,
  selectedModelId,
  productName,
  loadSample,
  runInspection,
  navigate,
  signal,
  FileConstructor = File,
}) {
  const blob = await loadSample(sample, { signal });
  throwIfAborted(signal);
  const file = new FileConstructor(
    [blob],
    sample.filename || `${sample.id}.jpg`,
    { type: sample.mediaType || blob.type || 'application/octet-stream' },
  );
  const record = await runInspection(file, selectedModelId, productName);
  throwIfAborted(signal);
  if (record) navigate({ to: '/inspect' });
  return record;
}

export const inspectSample = inspectShowcaseSample;
