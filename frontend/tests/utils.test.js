import assert from 'node:assert/strict';
import test from 'node:test';
import { toCsv } from '../src/utils/csv.js';
import { boxLabel, coordinate } from '../src/utils/format.js';
import { annotatedImageFilename, imageExtension } from '../src/utils/media.js';
import { appendModelId, modelClassesLabel, selectInitialModel } from '../src/utils/models.js';
import { scoreOf, severityScore } from '../src/utils/severity.js';

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

test('upload and stream use the canonical modelId multipart field', () => {
  const fields = [];
  const form = { append: (...args) => fields.push(args) };
  assert.equal(appendModelId(form, 'concrete-crack-yolov8'), form);
  appendModelId(form, '');
  assert.deepEqual(fields, [['modelId', 'concrete-crack-yolov8']]);
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
