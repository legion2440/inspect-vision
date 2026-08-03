import { useState } from 'react';
import Blueprint from './Blueprint.jsx';
import DefectOverlay from './DefectOverlay.jsx';

/** Image + canvas overlay + technical caption. Also renders the busy state. */
export default function InspectionViewer({
  src,
  defects = [],
  busy = false,
  caption,
  meta,
  selectedIndex,
}) {
  const [dims, setDims] = useState({ w: 0, h: 0 });

  return (
    <figure className="qc-figure">
      <Blueprint className="qc-figure-frame">
        <div className="qc-image-stack">
          <div className="duotone">
            <img
              src={src}
              alt="Inspected part"
              onLoad={(e) => setDims({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
            />
          </div>
          {!busy && dims.w > 0 && (
            <DefectOverlay
              defects={defects}
              sourceWidth={dims.w}
              sourceHeight={dims.h}
              selectedIndex={selectedIndex}
            />
          )}
          {busy && (
            <div className="qc-busy">
              <span className="qc-spinner" />
              <span className="qc-mono">RUNNING INFERENCE…</span>
            </div>
          )}
        </div>
        <figcaption className="qc-figcaption">
          <span className="qc-mono">
            {meta?.name || 'image'} · {dims.w}×{dims.h}
            {meta?.size ? ' · ' + (meta.size / 1048576).toFixed(1) + ' MB' : ''}
          </span>
          <span className="qc-mono">{caption || 'preprocess: resize 640² · grayscale · CLAHE'}</span>
        </figcaption>
      </Blueprint>
    </figure>
  );
}
