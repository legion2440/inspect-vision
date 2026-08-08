import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { toCsv } from '../src/utils/csv.js';
import { boxLabel, coordinate, modelLabel } from '../src/utils/format.js';
import {
  initialInspectionState,
  inspectionReducer,
} from '../src/context/inspectionState.js';
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

test('CSV export keeps the canonical columns and escapes values', () => {
  const csv = toCsv([
    {
      inspectionId: 'insp_1',
      timestamp: '2026-08-03T10:00:00Z',
      defects: [{ type: 'scratches,deep' }],
      totalDefects: 1,
      qualityScore: 84,
      status: 'failed',
    },
  ]);

  const [header, row] = csv.split('\n');
  assert.equal(
    header,
    'inspectionId,timestamp,defectCount,types,qualityScore,status',
  );
  assert.match(row, /^insp_1,2026-08-03T10:00:00Z,1,"scratches,deep",84,failed$/);
});

test('backend quality score is authoritative, including zero', () => {
  assert.equal(scoreOf({ qualityScore: 0, defects: [] }), 0);
  assert.equal(scoreOf({ qualityScore: 91, defects: [{ type: 'crazing' }] }), 91);
});

test('severity fallback uses real image area when available', () => {
  const defect = {
    type: 'crazing',
    confidence: 0.9,
    boundingBox: { x: 0, y: 0, width: 100, height: 100 },
  };
  const smallFrameScore = severityScore([defect], 200 * 200);
  const largeFrameScore = scoreOf({
    defects: [defect],
    imageWidth: 2000,
    imageHeight: 2000,
  });

  assert.ok(smallFrameScore < largeFrameScore);
  assert.equal(severityScore([], 1), 100);
});

test('client fallback uses neutral multi-model quality weight', () => {
  const defect = {
    type: 'crazing',
    confidence: 0.8,
    boundingBox: { x: 0, y: 0, width: 10, height: 10 },
  };

  assert.equal(severityScore([defect], 100 * 100), 91);
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
  assert.equal(appendModelId(form, 'bayespfl-general-v1'), form);
  assert.equal(appendProductName(form, '  capsule  '), form);
  appendModelId(form, '');
  appendProductName(form, '   ');
  assert.deepEqual(fields, [
    ['modelId', 'bayespfl-general-v1'],
    ['productName', 'capsule'],
  ]);
});

test('preprocessing labels follow the selected model profile', () => {
  assert.equal(
    preprocessingLabel({ preprocessingProfile: 'standard-color' }),
    'preprocess: letterbox 640² · color',
  );
  assert.equal(
    preprocessingLabel({ preprocessingProfile: 'steel-enhanced' }),
    'preprocess: letterbox 640² · grayscale · CLAHE',
  );
  assert.equal(
    preprocessingLabel({ preprocessingProfile: 'bayespfl-stretch' }),
    'preprocess: stretch 518² · CLIP normalization',
  );
});

test('model switch clears upload state and rejects a stale response', () => {
  const detecting = inspectionReducer(initialInspectionState, {
    type: 'file',
    preview: 'blob:steel',
    meta: { name: 'steel.jpg', size: 42 },
    requestId: 7,
  });
  const switched = inspectionReducer(detecting, {
    type: 'selectModel',
    modelId: 'concrete-crack-yolov8',
  });

  assert.equal(switched.selectedModelId, 'concrete-crack-yolov8');
  assert.equal(switched.current, null);
  assert.equal(switched.preview, null);
  assert.equal(switched.fileMeta, null);
  assert.equal(switched.error, null);
  assert.equal(switched.status, 'idle');
  assert.equal(switched.uploadRequestId, null);

  const afterStaleResponse = inspectionReducer(switched, {
    type: 'result',
    requestId: 7,
    record: { model: { id: 'neu-defect-yolov8' } },
  });
  assert.strictEqual(afterStaleResponse, switched);
});

test('installer command identifies the unavailable registry model', () => {
  assert.equal(
    installModelCommand('concrete-crack-yolov8'),
    'python scripts/install_models.py --model concrete-crack-yolov8',
  );
});

test('model class summary formats native names without semantic remapping', () => {
  assert.equal(
    modelClassesLabel({ classes: ['rolled_in_scale', 'pcb-short', 'crack'] }),
    'rolled in scale · pcb short · crack',
  );
});

test('annotated download filename follows the image media type', () => {
  assert.equal(imageExtension('data:image/jpeg;base64,AA=='), 'jpg');
  assert.equal(imageExtension('data:image/png;base64,AA=='), 'png');
  assert.equal(annotatedImageFilename('insp/unsafe', 'data:image/png;base64,AA=='), 'insp_unsafe.png');
  assert.equal(annotatedImageFilename('insp-1', '/media/annotated.jpeg?token=1'), 'insp-1.jpg');
  assert.equal(annotatedImageFilename('insp-2', 'data:application/octet-stream;base64,AA=='), 'insp-2');
});

test('coordinates are presented with at most one decimal place', () => {
  assert.equal(coordinate(12), '12');
  assert.equal(coordinate(12.04), '12');
  assert.equal(coordinate(12.06), '12.1');
  assert.equal(boxLabel({ x: 1.234, y: 2, width: 3.96, height: 4.01 }), '1.2, 2, 4, 4');
});

test('history model label uses display name and preserves retired-model fallback', () => {
  assert.equal(
    modelLabel({ model: { id: 'neu-defect-yolov8', displayName: 'Steel Surface' } }),
    'Steel Surface',
  );
  assert.equal(
    modelLabel({ model: { id: 'retired-manufacturing-model', displayName: 'retired-manufacturing-model' } }),
    'retired-manufacturing-model',
  );
  assert.equal(modelLabel({}), 'Unknown model');
});

test('showcase manifest produces three cards for each registered model domain', () => {
  const manifest = JSON.parse(readFileSync(
    new URL('../../backend/samples/showcase-samples.json', import.meta.url),
    'utf8',
  ));
  const groups = groupSamplesByDomain(manifest.samples);

  assert.equal(manifest.samples.length, 9);
  assert.deepEqual([...groups.values()].map((samples) => samples.length), [3, 3, 3]);
  assert.deepEqual(
    [...new Set(manifest.samples.map((sample) => sample.recommendedModelId))],
    ['factory-defect-guard-v6-mc', 'neu-defect-yolov8', 'concrete-crack-yolov8'],
  );
  const gkn = manifest.datasets.find((dataset) => dataset.id === 'gkn-blade-v1');
  assert.ok(gkn.sourceLabelVocabulary.includes('Nick'));
  assert.equal(manifest.samples.some((sample) => sample.sourceLabels.includes('Nick')), false);
  assert.deepEqual(
    manifest.samples
      .filter((sample) => sample.recommendedModelId === 'neu-defect-yolov8')
      .flatMap((sample) => sample.sourceLabels),
    ['Good', 'inclusion', 'Scratch'],
  );
});

test('showcase reports an unavailable recommended model without substituting another', () => {
  const sample = { recommendedModelId: 'concrete-crack-yolov8' };
  const models = [
    { id: 'factory-defect-guard-v6-mc', installed: true },
    { id: 'concrete-crack-yolov8', installed: false },
  ];

  assert.deepEqual(recommendedModelFor(sample, models), models[1]);
  assert.equal(recommendedModelFor({ recommendedModelId: 'retired' }, models), null);
});

test('inspect sample uses the current global model selection and navigates after success', async () => {
  const calls = [];
  class FakeFile {
    constructor(parts, name, options) {
      Object.assign(this, { parts, name, type: options.type });
    }
  }
  const sample = {
    id: 'concrete-demo',
    filename: 'concrete.jpg',
    mediaType: 'image/jpeg',
    recommendedModelId: 'concrete-crack-yolov8',
  };

  const record = await inspectShowcaseSample({
    sample,
    selectedModelId: 'neu-defect-yolov8',
    loadSample: async () => ({ type: 'image/jpeg', bytes: 'source' }),
    runInspection: async (file, modelId) => {
      calls.push({ file, modelId });
      return { inspectionId: 'insp-sample' };
    },
    navigate: (options) => calls.push({ navigate: options }),
    FileConstructor: FakeFile,
  });

  assert.equal(record.inspectionId, 'insp-sample');
  assert.equal(calls[0].modelId, 'neu-defect-yolov8');
  assert.equal(calls[0].file.name, 'concrete.jpg');
  assert.deepEqual(calls[1], { navigate: { to: '/inspect' } });
});

test('sample model switch aborts image loading before stale inference can start', async () => {
  let finishLoading;
  let loadOptions;
  let inferenceCalls = 0;
  let navigationCalls = 0;
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
    loadSample: async (_sample, options) => {
      loadOptions = options;
      await loadGate;
      return { type: 'image/jpeg' };
    },
    runInspection: async () => {
      inferenceCalls += 1;
      return { inspectionId: 'stale' };
    },
    navigate: () => { navigationCalls += 1; },
    signal: controller.signal,
    FileConstructor: FakeFile,
  });

  controller.abort();
  finishLoading();

  await assert.rejects(pending, (error) => error.name === 'AbortError');
  assert.strictEqual(loadOptions.signal, controller.signal);
  assert.equal(inferenceCalls, 0);
  assert.equal(navigationCalls, 0);
});

test('samples route cancels pending loads before changing the global model', () => {
  const route = readFileSync(new URL('../src/routes/samples.jsx', import.meta.url), 'utf8');
  assert.match(route, /sampleRequestRef\.current\?\.abort\(\)/);
  assert.match(route, /onChange=\{handleModelChange\}/);
  assert.match(route, /downscaled from source/);
  assert.match(route, /cropped from source/);
});

test('dashboard quick upload is wired to the shared selected model and context', () => {
  const dashboard = readFileSync(new URL('../src/routes/index.jsx', import.meta.url), 'utf8');
  assert.match(dashboard, /<ModelSelector[\s\S]*value=\{selectedModelId\}/);
  assert.match(dashboard, /runInspection\(file, selectedModelId, productName\)/);
});

test('inspect separates mode selection from the image file picker action', () => {
  const inspectRoute = readFileSync(new URL('../src/routes/inspect.jsx', import.meta.url), 'utf8');
  const uploader = readFileSync(new URL('../src/components/ImageUploader.jsx', import.meta.url), 'utf8');

  assert.match(inspectRoute, /Inspection mode/);
  assert.match(inspectRoute, /Image file/);
  assert.match(inspectRoute, /Live stream/);
  assert.doesNotMatch(inspectRoute, />\s*Upload\s*</);
  assert.match(uploader, /<button[\s\S]*Choose image[\s\S]*<input/);
  assert.match(uploader, /type="file"/);
  assert.doesNotMatch(uploader, /role="button"/);
});
