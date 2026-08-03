/**
 * Bundled mock of the FastAPI contract so the frontend runs standalone.
 * Set VITE_USE_MOCK=false once the backend is wired up.
 */
const SAMPLE = '/samples/sample-part.jpg';

const rec = (id, iso, defects, file) => ({
  inspectionId: id,
  timestamp: iso,
  fileName: file,
  imageUrl: SAMPLE,
  defects,
  totalDefects: defects.length,
  status: defects.length ? 'failed' : 'passed',
});

const box = (x, y, width, height) => ({ x, y, width, height });

let store = [
  rec('insp_20260803_004', '2026-08-03T14:38:12Z', [
    { type: 'scratch', confidence: 0.94, boundingBox: box(214, 168, 268, 96) },
    { type: 'dent', confidence: 0.86, boundingBox: box(690, 402, 152, 138) },
    { type: 'discoloration', confidence: 0.68, boundingBox: box(396, 588, 210, 128) },
  ], 'housing_04_2b.jpg'),
  rec('insp_20260803_003', '2026-08-03T14:12:47Z', [], 'housing_04_2a.jpg'),
  rec('insp_20260803_002', '2026-08-03T13:47:05Z', [
    { type: 'crack', confidence: 0.91, boundingBox: box(520, 240, 180, 210) },
  ], 'bracket_11c.jpg'),
  rec('insp_20260803_001', '2026-08-03T13:20:31Z', [
    { type: 'scratch', confidence: 0.79, boundingBox: box(120, 85, 245, 60) },
    { type: 'scratch', confidence: 0.72, boundingBox: box(640, 610, 190, 54) },
  ], 'panel_07.jpg'),
  rec('insp_20260802_014', '2026-08-02T17:58:09Z', [], 'panel_06.jpg'),
  rec('insp_20260802_013', '2026-08-02T17:31:22Z', [
    { type: 'dent', confidence: 0.83, boundingBox: box(410, 320, 210, 190) },
  ], 'housing_03_9f.jpg'),
  rec('insp_20260802_012', '2026-08-02T16:44:50Z', [
    { type: 'discoloration', confidence: 0.64, boundingBox: box(180, 470, 320, 180) },
    { type: 'dent', confidence: 0.88, boundingBox: box(760, 180, 160, 150) },
  ], 'flange_22.jpg'),
  rec('insp_20260802_011', '2026-08-02T16:02:18Z', [], 'flange_21.jpg'),
];

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export async function inspectImage(file) {
  await wait(1400);
  const id = 'insp_' + new Date().toISOString().slice(0, 10).replace(/-/g, '') + '_' + String(store.length + 1).padStart(3, '0');
  const pool = [
    { type: 'scratch', confidence: 0.93, boundingBox: box(200, 150, 250, 90) },
    { type: 'dent', confidence: 0.84, boundingBox: box(660, 390, 170, 150) },
    { type: 'discoloration', confidence: 0.66, boundingBox: box(380, 560, 220, 140) },
  ];
  const defects = pool.slice(0, 1 + Math.floor(Math.random() * 3));
  const record = { ...rec(id, new Date().toISOString(), defects, file?.name || 'upload.jpg'), imageUrl: URL.createObjectURL(file) };
  store = [record, ...store];
  return record;
}

export async function inspectFrame() {
  await wait(120);
  const jitter = () => Math.round((Math.random() - 0.5) * 60);
  return {
    defects: [
      { type: 'scratch', confidence: 0.9, boundingBox: box(300 + jitter(), 200 + jitter(), 240, 90) },
      { type: 'dent', confidence: 0.71, boundingBox: box(700 + jitter(), 380 + jitter(), 150, 140) },
    ],
  };
}

export async function getHistory() { await wait(250); return store; }

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
