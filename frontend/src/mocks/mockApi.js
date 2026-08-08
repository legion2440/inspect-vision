/** Bundled FastAPI-compatible mock for standalone frontend development. */
const SAMPLE = '/samples/sample-part.jpg';

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
    isDefault: true,
    installed: true,
  },
  {
    id: 'factory-defect-guard-v6-mc',
    displayName: 'General Manufacturing (YOLO)',
    role: 'general',
    domain: 'General manufacturing',
    description: 'Legacy multiclass coverage detector for several manufacturing domains.',
    classes: ['crazing', 'inclusion', 'patches', 'pitted_surface', 'rolled_in_scale', 'scratches', 'pcb_missing_hole', 'pcb_mouse_bite', 'pcb_open_circuit', 'pcb_short', 'pcb_spur', 'pcb_spurious_copper', 'tile_defect', 'transistor_defect', 'screw_defect', 'metal_nut_defect', 'capsule_defect'],
    preprocessingProfile: 'standard-color',
    requiresProductName: false,
    isDefault: false,
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
    isDefault: false,
    installed: true,
  },
];

const SAMPLE_DATASETS = [
  {
    id: 'defectdet-v1',
    name: 'DefectDet PCB Dataset',
    version: '1',
    sourceUrl: 'https://data.mendeley.com/datasets/t9d9zs3bmb/1',
    license: { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    attribution: 'DefectDet V1 contributors, licensed CC BY 4.0.',
  },
  {
    id: 'gkn-blade-v1',
    name: 'GKN Blade Surface Defect Dataset',
    version: '1',
    sourceUrl: 'https://data.mendeley.com/datasets/3bh998k78g/1',
    license: { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    attribution: 'GKN Blade Surface Defect Dataset V1 by Qianyu Zhou, licensed CC BY 4.0.',
  },
  {
    id: 'plos-neu-steel-figure-v1',
    name: 'Six Types of Metal Surface Defects, Figure 3',
    version: '1',
    sourceUrl: 'https://plos.figshare.com/articles/figure/Six_types_of_metal_surface_defects_/24767219',
    license: { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    attribution: 'Xu, Y., Jiao, P., & Liu, J. (2023). Figure 3. PLOS ONE. CC BY 4.0.',
  },
  {
    id: 'hu-infrastructure-cracks-v1',
    name: 'HU Infrastructure Cracks Dataset',
    version: '1',
    sourceUrl: 'https://zenodo.org/records/20829348',
    license: { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    attribution: 'HU Infrastructure Cracks Dataset, CC BY 4.0.',
  },
];

const MOCK_SAMPLES = [
  ['mock-pcb-open', 'General Manufacturing / PCB', 'factory-defect-guard-v6-mc', 'defectdet-v1', ['open circuit'], 'downscaled'],
  ['mock-pcb-short', 'General Manufacturing / PCB', 'factory-defect-guard-v6-mc', 'defectdet-v1', ['short circuit'], 'downscaled'],
  ['mock-pcb-copper', 'General Manufacturing / PCB', 'factory-defect-guard-v6-mc', 'defectdet-v1', ['spurious copper'], 'downscaled'],
  ['mock-steel-good', 'Steel Surface', 'neu-defect-yolov8', 'gkn-blade-v1', ['Good'], 'downscaled'],
  ['mock-steel-inclusion', 'Steel Surface', 'neu-defect-yolov8', 'plos-neu-steel-figure-v1', ['inclusion'], 'cropped'],
  ['mock-steel-scratch', 'Steel Surface', 'neu-defect-yolov8', 'gkn-blade-v1', ['Scratch'], null],
  ['mock-concrete-transverse', 'Concrete & Structural Cracks', 'concrete-crack-yolov8', 'hu-infrastructure-cracks-v1', ['pavement', 'transverse', 'moderate'], 'downscaled'],
  ['mock-concrete-longitudinal', 'Concrete & Structural Cracks', 'concrete-crack-yolov8', 'hu-infrastructure-cracks-v1', ['wall', 'longitudinal', 'severe'], 'downscaled'],
  ['mock-concrete-diagonal', 'Concrete & Structural Cracks', 'concrete-crack-yolov8', 'hu-infrastructure-cracks-v1', ['pavement', 'diagonal', 'severe'], 'downscaled'],
].map(([id, domain, recommendedModelId, datasetId, sourceLabels, assetTransform]) => ({
  id,
  domain,
  recommendedModelId,
  datasetId,
  sourceLabels,
  filename: 'sample-part.jpg',
  mediaType: 'image/jpeg',
  imageUrl: SAMPLE,
  width: 1600,
  height: 1187,
  ...(assetTransform ? { assetTransform } : {}),
}));

const modelOf = (modelId) => MODELS.find((model) => model.id === modelId) || MODELS[0];
const box = (x, y, width, height) => ({ x, y, width, height });

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
    return [{
      type: 'anomaly',
      confidence: live ? 0.75 : 0.76,
      boundingBox: box(300 + jitter(), 200 + jitter(), 240, 90),
    }];
  }
  if (model.id === 'concrete-crack-yolov8') {
    return [{
      type: 'crack',
      confidence: live ? 0.9 : 0.93,
      boundingBox: box((live ? 300 : 200) + jitter(), (live ? 200 : 150) + jitter(), live ? 240 : 250, 90),
    }];
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
  ], 'housing_04_2b.jpg', MODELS[2]),
  rec('insp_20260803_003', '2026-08-03T14:12:47Z', [], 'housing_04_2a.jpg', MODELS[2]),
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
    notice: 'Source labels describe dataset metadata, not model predictions.',
    datasets: SAMPLE_DATASETS,
    samples: MOCK_SAMPLES,
  };
}

export async function inspectImage(file, { modelId, productName } = {}) {
  await wait(1400);
  const model = modelOf(modelId);
  if (model.requiresProductName && !String(productName || '').trim()) {
    throw new Error('Product name is required for this detection model');
  }
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
  if (model.requiresProductName && !String(productName || '').trim()) {
    throw new Error('Product name is required for this detection model');
  }
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
