import assert from 'node:assert/strict';
import test from 'node:test';
import { inspectShowcaseSample } from '../src/utils/samples.js';

class FileStub {
  constructor(parts, name, options) {
    this.parts = parts;
    this.name = name;
    this.type = options?.type || '';
  }
}

test('showcase sample supplies category context without changing selected model', async () => {
  const calls = [];
  const navigation = [];
  const sample = {
    id: 'mvtec-screw-bad',
    filename: 'screw.png',
    mediaType: 'image/png',
    productName: 'Screw',
  };
  const blob = { type: 'image/png' };

  const record = await inspectShowcaseSample({
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
  assert.equal(calls[0][0].name, 'screw.png');
  assert.equal(calls[0][1], 'neu-defect-yolov8');
  assert.equal(calls[0][2], 'Screw');
  assert.deepEqual(navigation, [{ to: '/inspect' }]);
});
