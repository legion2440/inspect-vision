import assert from 'node:assert/strict';
import test from 'node:test';
import { inspectSample } from '../src/utils/samples.js';

class FileStub {
  constructor(parts, name, options) {
    this.parts = parts;
    this.name = name;
    this.type = options?.type || '';
  }
}

test('sample supplies category context without changing selected model', async () => {
  const calls = [];
  const navigation = [];
  const sample = {
    id: 'visa-candle-anomaly-0000',
    filename: 'candle.jpg',
    mediaType: 'image/jpeg',
    productName: 'Candle',
  };
  const blob = { type: 'image/jpeg' };

  const record = await inspectSample({
    sample,
    selectedModelId: 'neu-defect-yolov8',
    productName: sample.productName,
    loadSample: async () => blob,
    runInspection: async (...args) => {
      calls.push(args);
      return { inspectionId: 'insp_test' };
    },
    navigate: (target) => navigation.push(target),
    FileConstructor: FileStub,
  });

  assert.equal(record.inspectionId, 'insp_test');
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0].name, 'candle.jpg');
  assert.equal(calls[0][1], 'neu-defect-yolov8');
  assert.equal(calls[0][2], 'Candle');
  assert.deepEqual(navigation, [{ to: '/inspect' }]);
});
