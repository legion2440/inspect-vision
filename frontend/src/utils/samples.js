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

export async function inspectShowcaseSample({
  sample,
  selectedModelId,
  loadSample,
  runInspection,
  navigate,
  FileConstructor = File,
}) {
  const blob = await loadSample(sample);
  const file = new FileConstructor(
    [blob],
    sample.filename || `${sample.id}.jpg`,
    { type: sample.mediaType || blob.type || 'application/octet-stream' },
  );
  const record = await runInspection(file, selectedModelId);
  if (record) navigate({ to: '/inspect' });
  return record;
}
