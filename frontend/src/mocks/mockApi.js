/**
 * Bundled mock of the FastAPI contract so the frontend runs standalone.
 * Set VITE_USE_MOCK=false once the backend is wired up.
 */
const SAMPLE = '/samples/sample-part.jpg';

const MODELS = [
  {
    id: 'factory-defect-guard-v6-mc',
    displayName: 'General Manufacturing',
    role: 'general',
    domain: 'General manufacturing',
    description: 'Coverage-oriented detector for several manufacturing domains.',
    classes: ['crazing', 'inclusion', 'patches', 'pitted_surface', 'rolled_in_scale', 'scratches', 'pcb_missing_hole', 'pcb_mouse_bite', 'pcb_open_circuit', 'pcb_short', 'pcb_spur', 'pcb_spurious_copper', 'tile_defect', 'transistor_defect', 'screw_defect', 'metal_nut_defect', 'capsule_defect'],
    preprocessingProfile: 'standard-color',
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
    id: 'hu-infrastructure-cracks-v1',
    name: 'HU Infrastructure Cracks Dataset',
    version: '1',
    sourceUrl: 'https://zenodo.org/records/20829348',
    license: { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
    attribution: 'HU Infrastructure Cracks Dataset V1 contributors, licensed CC BY 4.0.',
  },
];

const MOCK_SAMPLES = [
  ['mock-pcb-open', 'General Manufacturing / PCB', 'factory-defect-guard-v6-mc', 'defectdet-v1', ['open circuit']],
  ['mock-pcb-short', 'General Manufacturing / PCB', 'factory-defect-guard-v6-mc', 'defectdet-v1', ['short circuit']],
  ['mock-pcb-copper', 'General Manufacturing / PCB', 'factory-defect-guard-v6-mc', 'defectdet-v1', ['spurious copper']],
  ['mock-steel-good', 'Steel Surface', 'neu-defect-yolov8', 'gkn-blade-v1', ['Good']],
  ['mock-steel-nick', 'Steel Surface', 'neu-defect-yolov8', 'gkn-blade-v1', ['Nick']],
  ['mock-steel-scratch', 'Steel Surface', 'neu-defect-yolov8', 'gkn-blade-v1', ['Scratch']],
  ['mock-concrete-transverse', 'Concrete & Structural Cracks', 'concrete-crack-yolov8', 'hu-infrastructure-cracks-v1', ['pavement', 'transverse']],
  ['mock-concrete-longitudinal', 'Concrete & Structural Cracks', 'concrete-crack-yolov8', 'hu-infrastructure-cracks-v1', ['wall', 'longitudinal']],
  ['mock-concrete-diagonal', 'Concrete & Structural Cracks', 'concrete-crack-yolov8', 'hu-infrastructure-cracks-v1', ['pavement', 'diagonal']],
].map(([id, domain, recommendedModelId, datasetId, sourceLabels]) => ({
  id,
  domain,
  recommendedModelId,
  datasetId,
  sourceLabels,
  filename: 'sample-part.jpg',
  mediaType: 'image/jpeg',
  imageUrl: SAMPLE,
}));

const modelOf = (modelId) => MODELS.find((model) => model.id === modelId) || MODELS[0];

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

const box = (x, y, width, height) => ({ x, y, width, height });

let store = [
  rec('insp_20260803_004', '2026-08-03T14:38:12Z', [
    { type: 'scratches', confidence: 0.94, boundingBox: box(214, 168, 268, 96) },
    { type: 'inclusion', confidence: 0.86, boundingBox: box(690, 402, 152, 138) },
    { type: 'pitted_surface', confidence: 0.68, boundingBox: box(396, 588, 210, 128) },
  ], 'housing_04_2b.jpg'),
  rec('insp_20260803_003', '2026-08-03T14:12:47Z', [], 'housing_04_2a.jpg'),
  rec('insp_20260803_002', '2026-08-03T13:47:05Z', [
    { type: 'crazing', confidence: 0.91, boundingBox: box(520, 240, 180, 210) },
  ], 'bracket_11c.jpg'),
  rec('insp_20260803_001', '2026-08-03T13:20:31Z', [
    { type: 'scratches', confidence: 0.79, boundingBox: box(120, 85, 245, 60) },
    { type: 'rolled-in_scale', confidence: 0.72, boundingBox: box(640, 610, 190, 54) },
  ], 'panel_07.jpg'),
  rec('insp_20260802_014', '2026-08-02T17:58:09Z', [], 'panel_06.jpg'),
  rec('insp_20260802_013', '2026-08-02T17:31:22Z', [
    { type: 'patches', confidence: 0.83, boundingBox: box(410, 320, 210, 190) },
  ], 'housing_03_9f.jpg'),
  rec('insp_20260802_012', '2026-08-02T16:44:50Z', [
    { type: 'pitted_surface', confidence: 0.64, boundingBox: box(180, 470, 320, 180) },
    { type: 'inclusion', confidence: 0.88, boundingBox: box(760, 180, 160, 150) },
  ], 'flange_22.jpg'),
  rec('insp_20260802_011', '2026-08-02T16:02:18Z', [], 'flange_21.jpg'),
];

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

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

export async function inspectImage(file, { modelId } = {}) {
  await wait(1400);
  const model = modelOf(modelId);
  const id = 'insp_' + new Date().toISOString().slice(0, 10).replace(/-/g, '') + '_' + String(store.length + 1).padStart(3, '0');
  const pool = model.id === 'concrete-crack-yolov8'
    ? [{ type: 'crack', confidence: 0.93, boundingBox: box(200, 150, 250, 90) }]
    : [
      { type: 'scratches', confidence: 0.93, boundingBox: box(200, 150, 250, 90) },
      { type: 'inclusion', confidence: 0.84, boundingBox: box(660, 390, 170, 150) },
      { type: 'crazing', confidence: 0.66, boundingBox: box(380, 560, 220, 140) },
    ];
  const defects = pool.slice(0, 1 + Math.floor(Math.random() * 3));
  const imageUrl = await dataUrlOf(file);
  const record = {
    ...rec(id, new Date().toISOString(), defects, file?.name || 'upload.jpg', model),
    imageUrl,
    originalImageUrl: imageUrl,
  };
  store = [record, ...store];
  return record;
}

export async function inspectFrame({ modelId } = {}) {
  await wait(120);
  const model = modelOf(modelId);
  const jitter = () => Math.round((Math.random() - 0.5) * 60);
  const defects = model.id === 'concrete-crack-yolov8'
    ? [{ type: 'crack', confidence: 0.9, boundingBox: box(300 + jitter(), 200 + jitter(), 240, 90) }]
    : [
      { type: 'scratches', confidence: 0.9, boundingBox: box(300 + jitter(), 200 + jitter(), 240, 90) },
      { type: 'inclusion', confidence: 0.71, boundingBox: box(700 + jitter(), 380 + jitter(), 150, 140) },
    ];
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
  const found = store.find((r) => r.inspectionId === id);
  if (!found) throw new Error('Inspection not found');
  return found;
}

export async function deleteInspection(id) {
  await wait(150);
  store = store.filter((r) => r.inspectionId !== id);
  return { deleted: id };
}

export async function clearHistory() { await wait(150); store = []; return { cleared: true }; }
