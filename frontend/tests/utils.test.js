import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { toCsv } from '../src/utils/csv.js';
import { boxLabel, coordinate, modelLabel } from '../src/utils/format.js';
import { initialInspectionState, inspectionReducer } from '../src/context/inspectionState.js';
import { annotatedImageFilename, imageExtension } from '../src/utils/media.js';
import {
  appendModelId,
  appendProductName,
  installModelCommand,
  modelClassesLabel,
  preprocessingLabel,
  selectInitialModel,
} from '../src/utils/models.js';
import { scoreOf, severityScore } from '../src/utils/severity.js';
import {
  groupSamplesByDomain,
  inspectShowcaseSample,
  recommendedModelFor,
} from '../src/utils/samples.js';

test('CSV export keeps canonical columns and escaping', () => {
  const csv = toCsv([{
    inspectionId: 'insp_1',
    timestamp: '2026-08-03T10:00:00Z',
    defects: [{ type: 'scratches,deep' }],
    totalDefects: 1,
    qualityScore: 84,
    status: 'failed',
  }]);
  const [header, row] = csv.split('\n');
  assert.equal(header, 'inspectionId,timestamp,defectCount,types,qualityScore,status');
  assert.match(row, /^insp_1,2026-08-03T10:00:00Z,1,"scratches,deep",84,failed$/);
});

test('backend quality score remains authoritative', () => {
  assert.equal(scoreOf({ qualityScore: 0, defects: [] }), 0);
  assert.equal(scoreOf({ qualityScore: 91, defects: [{ type: 'crazing' }] }), 91);
});

test('severity fallback uses real image area', () => {
  const defect = {
    type: 'crazing',
    confidence: 0.9,
    boundingBox: { x: 0, y: 0, width: 100, height: 100 },
  };
  assert.ok(severityScore([defect], 200 * 200) < scoreOf({
    defects: [defect],
    imageWidth: 2000,
    imageHeight: 2000,
  }));
  assert.equal(severityScore([], 1), 100);
});

test('model selection prefers the installed API default', () => {
  const models = [
    { id: 'steel', isDefault: false, installed: true },
    { id: 'broad', isDefault: true, installed: true },
  ];
  assert.equal(selectInitialModel(models), 'broad');
  assert.equal(selectInitialModel([{ id: 'broad', isDefault: true, installed: false }, models[0]]), 'steel');
});

test('upload and stream use canonical guided multipart fields', () => {
  const fields = [];
  const form = { append: (...args) => fields.push(args) };
  appendModelId(form, 'bayespfl-general-v1');
  appendProductName(form, '  capsule  ');
  appendModelId(form, '');
  appendProductName(form, '   ');
  assert.deepEqual(fields, [
    ['modelId', 'bayespfl-general-v1'],
    ['productName', 'capsule'],
  ]);
});

test('preprocessing labels follow the selected model profile', () => {
  assert.equal(preprocessingLabel({ preprocessingProfile: 'standard-color' }), 'preprocess: letterbox 640² · color');
  assert.equal(preprocessingLabel({ preprocessingProfile: 'steel-enhanced' }), 'preprocess: letterbox 640² · grayscale · CLAHE');
  assert.equal(preprocessingLabel({ preprocessingProfile: 'bayespfl-stretch' }), 'preprocess: stretch 518² · CLIP normalization');
});

test('model switch clears upload state and rejects a stale response', () => {
  const detecting = inspectionReducer(initialInspectionState, {
    type: 'file', preview: 'blob:steel', meta: { name: 'steel.jpg', size: 42 }, requestId: 7,
  });
  const switched = inspectionReducer(detecting, {
    type: 'selectModel', modelId: 'concrete-crack-yolov8',
  });
  assert.equal(switched.selectedModelId, 'concrete-crack-yolov8');
  assert.equal(switched.current, null);
  assert.equal(switched.preview, null);
  assert.equal(switched.uploadRequestId, null);
  assert.strictEqual(inspectionReducer(switched, {
    type: 'result', requestId: 7, record: { model: { id: 'neu-defect-yolov8' } },
  }), switched);
});

test('model helpers preserve installer, classes and media naming', () => {
  assert.equal(
    installModelCommand('concrete-crack-yolov8'),
    'python scripts/install_models.py --model concrete-crack-yolov8',
  );
  assert.equal(
    modelClassesLabel({ classes: ['rolled_in_scale', 'pcb-short', 'crack'] }),
    'rolled in scale · pcb short · crack',
  );
  assert.equal(imageExtension('data:image/png;base64,AA=='), 'png');
  assert.equal(annotatedImageFilename('insp/unsafe', 'data:image/png;base64,AA=='), 'insp_unsafe.png');
});

test('coordinate and history labels remain stable', () => {
  assert.equal(coordinate(12.06), '12.1');
  assert.equal(boxLabel({ x: 1.234, y: 2, width: 3.96, height: 4.01 }), '1.2, 2, 4, 4');
  assert.equal(modelLabel({ model: { id: 'neu-defect-yolov8', displayName: 'Steel Surface' } }), 'Steel Surface');
  assert.equal(modelLabel({}), 'Unknown model');
});

test('VisA audit corpus still contains twelve tracked local images', () => {
  const manifest = JSON.parse(readFileSync(
    new URL('../../backend/samples/demo-samples.json', import.meta.url),
    'utf8',
  ));
  assert.equal(manifest.dataset.id, 'visa');
  assert.equal(manifest.selection.sampleCount, 12);
  assert.equal(manifest.files.length, 12);
  assert.ok(manifest.files.every((sample) => sample.path.startsWith('backend/samples/demo/')));
});

test('sample recommendation never substitutes another model', () => {
  const models = [
    { id: 'factory-defect-guard-v6-mc', installed: true },
    { id: 'concrete-crack-yolov8', installed: false },
  ];
  assert.deepEqual(
    recommendedModelFor({ recommendedModelId: 'concrete-crack-yolov8' }, models),
    models[1],
  );
  assert.equal(recommendedModelFor({ recommendedModelId: 'retired' }, models), null);
});

test('showcase inspection uses the current global model selection', async () => {
  const calls = [];
  class FakeFile {
    constructor(parts, name, options) {
      Object.assign(this, { parts, name, type: options.type });
    }
  }
  const record = await inspectShowcaseSample({
    sample: { id: 'screw-demo', filename: 'screw.png', mediaType: 'image/png' },
    selectedModelId: 'neu-defect-yolov8',
    loadSample: async () => ({ type: 'image/png' }),
    runInspection: async (file, modelId) => {
      calls.push({ file, modelId });
      return { inspectionId: 'insp-sample' };
    },
    navigate: (options) => calls.push({ navigate: options }),
    FileConstructor: FakeFile,
  });
  assert.equal(record.inspectionId, 'insp-sample');
  assert.equal(calls[0].modelId, 'neu-defect-yolov8');
  assert.equal(calls[0].file.name, 'screw.png');
  assert.deepEqual(calls[1], { navigate: { to: '/inspect' } });
});

test('sample model switch aborts loading before stale inference', async () => {
  let finishLoading;
  let inferenceCalls = 0;
  const controller = new AbortController();
  const loadGate = new Promise((resolve) => { finishLoading = resolve; });
  class FakeFile {
    constructor(parts, name, options) {
      Object.assign(this, { parts, name, type: options.type });
    }
  }
  const pending = inspectShowcaseSample({
    sample: { id: 'steel-demo', filename: 'steel.jpg', mediaType: 'image/jpeg' },
    selectedModelId: 'neu-defect-yolov8',
    loadSample: async () => { await loadGate; return { type: 'image/jpeg' }; },
    runInspection: async () => { inferenceCalls += 1; return { inspectionId: 'stale' }; },
    navigate: () => {},
    signal: controller.signal,
    FileConstructor: FakeFile,
  });
  controller.abort();
  finishLoading();
  await assert.rejects(pending, (error) => error.name === 'AbortError');
  assert.equal(inferenceCalls, 0);
});

test('samples route keeps the curated showcase separate from VisA audit corpus', () => {
  const route = readFileSync(new URL('../src/routes/samples.jsx', import.meta.url), 'utf8');
  assert.match(route, /Curated inspection showcase/);
  assert.match(route, /Checked Bayes-PFL product examples plus steel and concrete specialist cases/);
  assert.doesNotMatch(route, /Twelve local VisA demo images/);
  assert.match(route, /onChange=\{handleModelChange\}/);
  assert.match(route, /const sampleProductName = sample\.productName \|\| productName/);
  assert.doesNotMatch(route, /selectModel\(sample\.recommendedModelId\)/);
  assert.match(route, /Use suggested model/);
});

test('guided category control remains an editable combobox', () => {
  const selector = readFileSync(new URL('../src/components/ModelSelector.jsx', import.meta.url), 'utf8');
  assert.match(selector, /role="combobox"/);
  assert.match(selector, /role="listbox"/);
  assert.match(selector, /Custom values are allowed/);
  assert.doesNotMatch(selector, /<datalist/);
});

test('viewer, dashboard and inspect route preserve their contracts', () => {
  const viewer = readFileSync(new URL('../src/components/InspectionViewer.jsx', import.meta.url), 'utf8');
  const dashboard = readFileSync(new URL('../src/routes/index.jsx', import.meta.url), 'utf8');
  const inspectRoute = readFileSync(new URL('../src/routes/inspect.jsx', import.meta.url), 'utf8');
  const uploader = readFileSync(new URL('../src/components/ImageUploader.jsx', import.meta.url), 'utf8');
  assert.match(viewer, /Original ·/);
  assert.match(viewer, /Model input ·/);
  assert.match(dashboard, /<ModelSelector[\s\S]*value=\{selectedModelId\}/);
  assert.match(dashboard, /runInspection\(file, selectedModelId, productName\)/);
  assert.match(inspectRoute, /Inspection mode/);
  assert.match(inspectRoute, /Live stream/);
  assert.match(uploader, /type="file"/);
});
