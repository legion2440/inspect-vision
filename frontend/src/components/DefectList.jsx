import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { confidenceColor } from '../utils/colors.js';
import { pct } from '../utils/format.js';

/** Defect rows: type + icon, color-coded confidence, coordinates. */
export default function DefectList({ defects = [], onSelect, selectedIndex }) {
  if (!defects.length) {
    return (
      <div className="qc-empty">
        <CheckCircle2 size={18} strokeWidth={1.5} />
        <span>No defects detected — part within tolerance.</span>
      </div>
    );
  }

  return (
    <div>
      {defects.map((d, i) => (
        <button
          type="button"
          key={i}
          className={'qc-defect' + (selectedIndex === i ? ' is-active' : '')}
          onMouseEnter={() => onSelect?.(i)}
          onMouseLeave={() => onSelect?.(null)}
          onFocus={() => onSelect?.(i)}
        >
          <span className="qc-mono qc-defect-idx">{String(i + 1).padStart(2, '0')}</span>
          <span className="qc-defect-body">
            <span className="qc-defect-head">
              <span className="qc-defect-type">
                <AlertTriangle size={15} strokeWidth={1.5} color="var(--color-accent-700)" />
                {d.type}
              </span>
              <span className="qc-mono" style={{ color: confidenceColor(d.confidence) }}>
                {pct(d.confidence)}
              </span>
            </span>
            <span className="qc-bar">
              <span
                className="qc-bar-fill"
                style={{ width: pct(d.confidence), background: confidenceColor(d.confidence) }}
              />
            </span>
            <span className="qc-mono qc-defect-coords">
              x {d.boundingBox.x} · y {d.boundingBox.y} · w {d.boundingBox.width} · h {d.boundingBox.height}
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}
