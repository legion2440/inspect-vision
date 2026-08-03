import assert from 'node:assert/strict';
import test from 'node:test';
import { toCsv } from '../src/utils/csv.js';
import { scoreOf, severityScore } from '../src/utils/severity.js';

test('CSV export keeps the canonical columns and escapes values', () => {
  const csv = toCsv([
    {
      inspectionId: 'insp_1',
      timestamp: '2026-08-03T10:00:00Z',
      defects: [{ type: 'scratch,deep' }],
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
  assert.match(row, /^insp_1,2026-08-03T10:00:00Z,1,"scratch,deep",84,failed$/);
});

test('backend quality score is authoritative, including zero', () => {
  assert.equal(scoreOf({ qualityScore: 0, defects: [] }), 0);
  assert.equal(scoreOf({ qualityScore: 91, defects: [{ type: 'crack' }] }), 91);
});

test('severity fallback uses real image area when available', () => {
  const defect = {
    type: 'crack',
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
