/** Bundled FastAPI-compatible mock for standalone frontend development. */
const SAMPLE = '/samples/sample-part.jpg';

const PRODUCT_PRESETS = [
  ['Bottle', 'local'],
  ['Capsule', 'local'],
  ['Screw', 'local'],
  ['Metal nut', 'local'],
  ['Hazelnut', 'upstream'],
  ['Pill', 'upstream'],
  ['Toothbrush', 'upstream'],
  ['Tile', 'upstream'],
  ['Wood', 'upstream'],
  ['Carpet', 'upstream'],
  ['Steel surface', 'comparison'],
  ['Concrete surface', 'comparison'],
].map(([value, evidence]) => ({ value, evidence }));

const MODELS = [
  {
    id: 'bayespfl-general-v1',
    displayName: 'General Manufacturing (Bayes-PFL)',
    role: 'general',
    domain: 'Cross-domain manufacturing anomaly localization',
    description: 'Category-guided anomaly localization for varied manufactured products; specialists remain preferable for supported known domains.',
    classes: ['anomaly'],
    preprocessingProfile: 'bayespfl-stretch',
    requiresProductName: true,
    productNamePresets: PRODUCT_PRESETS,
    isDefault: true,
    installed: true,
  },
  {
    id: 'neu-defect-yolov8',
    displayName: 'Steel Surface',
    role: 'specialist',
    domain: 'Steel surface',
    description: 'Specialist detector for six steel surface defect classes.',
    classes: ['crazing', 'inclusion', 'patches', 'pitted_surface', 'rolled-in_scale', 'scratches'],
    preprocessingProfile: 'steel-enhanced',
    requiresProductName: false,
    productNamePresets: [],
    isDefault: false,
    installed: true,
  },
  {
    id: 'concrete-crack-yolov8',
    displayName: 'Concrete & Structural Cracks',
    role: 'specialist',
    domain: 'Concrete and structural surfaces',
    description: 'Specialist detector for visible cracks on concrete and masonry.',
    classes: ['crack'],
    preprocessingProfile: 'standard-color',
    requiresProductName: false,
    productNamePresets: [],
    isDefault: false,
    installed: true,
  },
];

const SAMPLE_DATASETS = [{
  id: 'visa',
  name: 'Visual Anomaly (VisA)',
  version: '1.0',
  sourceUrl: 'https://github.com/amazon-science/spot-diff',
  license: { name: 'CDLA-Permissive-2.0', url: 'https://cdla.dev/permissive-2-0/' },
  attribution: 'Visual Anomaly (VisA) tracked demo subset.',
}];

const MOCK_SAMPLES = [
  ['mock-candle-good', 'Candle', 'good', ['normal']],
  ['mock-candle-bad-1', 'Candle', 'bad', ['anomaly']],
  ['mock-candle-bad-2', 'Candle', 'bad', ['anomaly']],
  ['mock-capsules-good', 'Capsules', 'good', ['normal']],
  ['mock-capsules-bad-1', 'Capsules', 'bad', ['anomaly']],
  ['mock-capsules-bad-2', 'Capsules', 'bad', ['anomaly']],
  ['mock-cashew-good', 'Cashew', 'good', ['normal']],
  ['mock-cashew-bad-1', 'Cashew', 'bad', ['anomaly']],
  ['mock-cashew-bad-2', 'Cashew', 'bad', ['anomaly']],
  ['mock-chewing-gum-good', 'Chewing gum', 'good', ['normal']],
  ['mock-chewing-gum-bad-1', 'Chewing gum', 'bad', ['anomaly']],
  ['mock-chewing-gum-bad-2', 'Chewing gum', 'bad', ['anomaly']],
].map(([id, productName, condition, sourceLabels]) => ({
  id,
  domain: productName,
  productName,
  condition,
  recommendedModelId: 'bayespfl-general-v1',
  datasetId: 'visa',
  sourceLabels,
  sourcePath: `backend/samples/demo/${id}.jpg`,
  filename: 'sample-part.jpg',
  mediaType: 'image/jpeg',
  imageUrl: SAMPLE,
}));

const modelOf = (modelId) => MODELS.find((model) => model.id === modelId) || MODELS[0];
const box = (x, y, width, height) => ({ x, y, width, height });

function normalizeProductName(value) {
  const normalized = String(value || '').trim().replaceAll('_', ' ').replace(/\s+/g, ' ').toLowerCase();
  if (!normalized) throw new Error('Product / category is required for Bayes-PFL');
  if (normalized.length < 2 || normalized.length > 40) throw new Error('Product / category must be between 2 and 40 characters');
  if (normalized.split(' ').length > 3) throw new Error('Product / category must contain at most 3 words');
  if (!/^[a-z]+(?:[ -][a-z]+)*$/.test(normalized)) throw new Error('Product / category may contain only Latin letters, spaces, hyphens, or underscores');
  return normalized;
}

const rec = (id, iso, defects, file, model = MODELS[0]) => ({
  inspectionId: id,
  timestamp: iso,
  fileName: file,
  imageUrl: SAMPLE,
  originalImageUrl: SAMPLE,
  imageWidth: 1600,
  imageHeight: 1187,
  defects,
  totalDefects: defects.length,
  qualityScore: defects.length ? 80 : 100,
  status: defects.length ? 'failed' : 'passed',
  model: { id: model.id, displayName: model.displayName },
});

const mockDefectPool = (model, { live = false, jitter = () => 0 } = {}) => {
  if (model.id === 'bayespfl-general-v1') {
    return [{ type: 'anomaly', confidence: live ? 0.75 : 0.76, boundingBox: box(300 + jitter(), 200 + jitter(), 240, 90) }];
  }
  if (model.id === 'concrete-crack-yolov8') {
    return [{ type: 'crack', confidence: live ? 0.9 : 0.93, boundingBox: box((live ? 300 : 200) + jitter(), (live ? 200 : 150) + jitter(), live ? 240 : 250, 90) }];
  }
  if (live) {
    return [
      { type: 'scratches', confidence: 0.9, boundingBox: box(300 + jitter(), 200 + jitter(), 240, 90) },
      { type: 'inclusion', confidence: 0.71, boundingBox: box(700 + jitter(), 380 + jitter(), 150, 140) },
    ];
  }
  return [
    { type: 'scratches', confidence: 0.93, boundingBox: box(200, 150, 250, 90) },
    { type: 'inclusion', confidence: 0.84, boundingBox: box(660, 390, 170, 150) },
  ];
};

let store = [
  rec('insp_20260803_004', '2026-08-03T14:38:12Z', [
    { type: 'scratches', confidence: 0.94, boundingBox: box(214, 168, 268, 96) },
  ], 'housing_04_2b.jpg', MODELS[1]),
  rec('insp_20260803_003', '2026-08-03T14:12:47Z', [], 'housing_04_2a.jpg', MODELS[1]),
];

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const dataUrlOf = (file) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.addEventListener('load', () => resolve(reader.result), { once: true });
  reader.addEventListener('error', () => reject(new Error('Could not read selected image')), { once: true });
  reader.readAsDataURL(file);
});

export async function getModels() {
  await wait(80);
  return MODELS;
}

export async function getSamples() {
  await wait(80);
  return {
    notice: 'Source labels describe VisA dataset ground truth, not model predictions.',
    datasets: SAMPLE_DATASETS,
    samples: MOCK_SAMPLES,
  };
}

export async function inspectImage(file, { modelId, productName } = {}) {
  await wait(1400);
  const model = modelOf(modelId);
  if (model.requiresProductName) normalizeProductName(productName);
  const id = 'insp_' + new Date().toISOString().slice(0, 10).replace(/-/g, '') + '_' + String(store.length + 1).padStart(3, '0');
  const pool = mockDefectPool(model);
  const defects = pool.slice(0, 1 + Math.floor(Math.random() * pool.length));
  const imageUrl = await dataUrlOf(file);
  const record = {
    ...rec(id, new Date().toISOString(), defects, file?.name || 'upload.jpg', model),
    imageUrl,
    originalImageUrl: imageUrl,
  };
  store = [record, ...store];
  return record;
}

export async function inspectFrame({ modelId, productName } = {}) {
  await wait(120);
  const model = modelOf(modelId);
  if (model.requiresProductName) normalizeProductName(productName);
  const jitter = () => Math.round((Math.random() - 0.5) * 60);
  const defects = mockDefectPool(model, { live: true, jitter });
  return {
    frameWidth: 1280,
    frameHeight: 720,
    defects,
    totalDefects: defects.length,
    qualityScore: 80,
    status: defects.length ? 'failed' : 'passed',
    model: { id: model.id, displayName: model.displayName },
  };
}

export async function getHistory(filters = {}) {
  await wait(250);
  return store.filter((record) => {
    const day = String(record.timestamp || '').slice(0, 10);
    if (filters.from && day < filters.from) return false;
    if (filters.to && day > filters.to) return false;
    if (filters.type && filters.type !== 'all' && !record.defects.some((d) => d.type === filters.type)) return false;
    if (filters.q) {
      const haystack = (record.inspectionId + ' ' + (record.fileName || '')).toLowerCase();
      if (!haystack.includes(String(filters.q).toLowerCase())) return false;
    }
    return true;
  });
}

export async function getInspection(id) {
  await wait(200);
  const found = store.find((record) => record.inspectionId === id);
  if (!found) throw new Error('Inspection not found');
  return found;
}

export async function deleteInspection(id) {
  await wait(150);
  store = store.filter((record) => record.inspectionId !== id);
  return { inspectionId: id, deleted: true };
}

export async function clearHistory() {
  await wait(150);
  const cleared = store.length;
  store = [];
  return { cleared };
}
