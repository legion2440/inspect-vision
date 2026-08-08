import { scoreColor } from '../utils/colors.js';

/** Bonus: quality score 0-100 with a color-coded indicator. */
export default function SeverityScore({ score }) {
  return (
    <div>
      <div className="qc-score-head">
        <h6>Quality score</h6>
        <span className="qc-mono">{score} / 100</span>
      </div>
      <div className="qc-bar qc-bar-lg">
        <span className="qc-bar-fill" style={{ width: score + '%', background: scoreColor(score) }} />
      </div>
      <p className="text-muted qc-note">Reduced by defect class, count and area relative to the part.</p>
    </div>
  );
}
