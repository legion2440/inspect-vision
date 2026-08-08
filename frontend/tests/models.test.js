import assert from 'node:assert/strict';
import test from 'node:test';
import { inspectionReducer, initialInspectionState } from '../src/context/inspectionState.js';
import { getModels, inspectFrame } from '../src/mocks/mockApi.js';

test('frontend registry fixture exposes Bayes-PFL and two specialists', async () => {
  const models = await getModels();

  assert.equal(models.length, 3);
  assert.deepEqual(models.map((model) => model.id), [
    'bayespfl-general-v1',
    'neu-defect-yolov8',
    'concrete-crack-yolov8',
  ]);
  assert.equal(models.find((model) => model.isDefault)?.id, 'bayespfl-general-v1');
  assert.equal(models[0].requiresProductName, true);
  assert.equal(models[0].classes[0], 'anomaly');
  assert.equal(models[0].productNamePresets.length, 12);
  assert.ok(models[0].productNamePresets.some((preset) => preset.value === 'Steel surface'));
  assert.ok(models[0].productNamePresets.some((preset) => preset.value === 'Concrete surface'));
  assert.ok(!models[0].productNamePresets.some((preset) => preset.value === 'Cable'));
  assert.ok(!models[0].productNamePresets.some((preset) => preset.value === 'Zipper'));
});

test('Bayes-PFL selection follows the existing generic reducer path', async () => {
  const models = await getModels();
  const loaded = inspectionReducer(initialInspectionState, { type: 'models', models });
  const steel = inspectionReducer(loaded, {
    type: 'selectModel',
    modelId: 'neu-defect-yolov8',
  });
  const bayes = inspectionReducer(steel, {
    type: 'selectModel',
    modelId: 'bayespfl-general-v1',
  });

  assert.equal(loaded.selectedModelId, 'bayespfl-general-v1');
  assert.equal(steel.selectedModelId, 'neu-defect-yolov8');
  assert.equal(bayes.selectedModelId, 'bayespfl-general-v1');
});

test('Bayes-PFL mock inference validates category context and emits native anomaly', async () => {
  await assert.rejects(
    inspectFrame({ modelId: 'bayespfl-general-v1' }),
    /Product \/ category is required/,
  );
  await assert.rejects(
    inspectFrame({ modelId: 'bayespfl-general-v1', productName: 'хуй' }),
    /Latin letters/,
  );
  const result = await inspectFrame({
    modelId: 'bayespfl-general-v1',
    productName: 'metal_nut',
  });

  assert.equal(result.model.id, 'bayespfl-general-v1');
  assert.ok(result.defects.length > 0);
  assert.deepEqual(new Set(result.defects.map((defect) => defect.type)), new Set(['anomaly']));
});
