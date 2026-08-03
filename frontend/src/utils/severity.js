import { QUALITY_CLASS_WEIGHTS } from './defectTypes.js';

/**
 * Quality score 0-100. Each defect costs its class weight, scaled by how much
 * of the frame it covers and by detection confidence; more defects compound.
 * Used as a client-side fallback when the backend omits qualityScore.
 */
export function severityScore(defects = [], imageArea = 1280 * 854) {
  if (!defects.length) return 100;
  const penalty = defects.reduce((sum, d) => {
    const weight = QUALITY_CLASS_WEIGHTS[d.type];
    if (weight == null) throw new Error('Unknown quality weight for defect type: ' + d.type);
    const b = d.boundingBox || {};
    const areaRatio = Math.min(1, Math.max(0, ((b.width || 0) * (b.height || 0)) / imageArea));
    return sum + weight * (d.confidence ?? 0) * (10 + 90 * areaRatio);
  }, 0);
  return Math.max(0, Math.min(100, Math.round(100 - penalty)));
}

export const scoreOf = (rec) => {
  if (rec?.qualityScore != null) return rec.qualityScore;
  const imageArea = rec?.imageWidth && rec?.imageHeight
    ? rec.imageWidth * rec.imageHeight
    : 1280 * 854;
  return severityScore(rec?.defects || [], imageArea);
};
