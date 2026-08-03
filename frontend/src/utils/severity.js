const WEIGHTS = { crack: 1.0, dent: 0.75, scratch: 0.5, discoloration: 0.35 };

/**
 * Quality score 0-100. Each defect costs its class weight, scaled by how much
 * of the frame it covers and by detection confidence; more defects compound.
 * Used as a client-side fallback when the backend omits qualityScore.
 */
export function severityScore(defects = [], imageArea = 1280 * 854) {
  if (!defects.length) return 100;
  const penalty = defects.reduce((sum, d) => {
    const w = WEIGHTS[d.type] ?? 0.5;
    const b = d.boundingBox || {};
    const area = ((b.width || 0) * (b.height || 0)) / imageArea;
    const size = Math.min(1, area * 12);
    return sum + w * (0.55 + 0.45 * size) * (0.6 + 0.4 * (d.confidence ?? 0.8)) * 26;
  }, 0);
  return Math.max(0, Math.round(100 - penalty));
}

export const scoreOf = (rec) =>
  rec?.qualityScore ?? severityScore(rec?.defects || []);
