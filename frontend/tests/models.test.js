import assert from 'node:assert/strict';
import test from 'node:test';
import { inspectionReducer, initialInspectionState } from '../src/context/inspectionState.js';
import { getModels, inspectFrame } from '../src/mocks/mockApi.js';

test('frontend registry fixture exposes Bayes-PFL as the default general model', async () => {
  const models = await getModels();

  assert.equal(models.length, 4);
  assert.deepEqual(models.map((model) => model.id), [
    'bayespfl-general-v1',
    'factory-defect-guard-v6-mc',
    'neu-defect-yolov8',
    'concrete-crack-yolov8',
  ]);
  assert.equal(models.find((model) => model.isDefault)?.id, 'bayespfl-general-v1');
  assert.deepEqual(models[0], {
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
  });
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

test('Bayes-PFL mock inference requires a category and emits native anomaly', async () => {
  await assert.rejects(
    inspectFrame({ modelId: 'bayespfl-general-v1' }),
    /Product name is required/,
  );
  const result = await inspectFrame({
    modelId: 'bayespfl-general-v1',
    productName: 'metal_nut',
  });

  assert.equal(result.model.id, 'bayespfl-general-v1');
  assert.ok(result.defects.length > 0);
  assert.deepEqual(new Set(result.defects.map((defect) => defect.type)), new Set(['anomaly']));
});
