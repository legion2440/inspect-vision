import assert from 'node:assert/strict';
import test from 'node:test';
import { inspectionReducer, initialInspectionState } from '../src/context/inspectionState.js';
import { getModels } from '../src/mocks/mockApi.js';

test('the generic frontend registry fixture exposes AnomalyCLIP as a fourth model', async () => {
  const models = await getModels();

  assert.equal(models.length, 4);
  assert.deepEqual(models.map((model) => model.id), [
    'factory-defect-guard-v6-mc',
    'neu-defect-yolov8',
    'concrete-crack-yolov8',
    'anomalyclip-general-v1',
  ]);
  assert.equal(models.find((model) => model.isDefault)?.id, 'factory-defect-guard-v6-mc');
  assert.deepEqual(models[3], {
    id: 'anomalyclip-general-v1',
    displayName: 'General Manufacturing (AnomalyCLIP v1)',
    role: 'general',
    domain: 'Cross-domain manufacturing anomaly localization',
    description: 'Broad anomaly localization with generic anomaly output and no subtype classification; specialist models are preferred for known domains.',
    classes: ['anomaly'],
    preprocessingProfile: 'anomalyclip-stretch',
    isDefault: false,
    installed: true,
  });
});

test('AnomalyCLIP selection and switching back use the existing generic reducer path', async () => {
  const models = await getModels();
  const loaded = inspectionReducer(initialInspectionState, { type: 'models', models });
  const anomalyclip = inspectionReducer(loaded, {
    type: 'selectModel',
    modelId: 'anomalyclip-general-v1',
  });
  const steel = inspectionReducer(anomalyclip, {
    type: 'selectModel',
    modelId: 'neu-defect-yolov8',
  });

  assert.equal(loaded.selectedModelId, 'factory-defect-guard-v6-mc');
  assert.equal(anomalyclip.selectedModelId, 'anomalyclip-general-v1');
  assert.equal(steel.selectedModelId, 'neu-defect-yolov8');
});
