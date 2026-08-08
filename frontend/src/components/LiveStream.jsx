import Blueprint from './Blueprint.jsx';
import DefectOverlay from './DefectOverlay.jsx';
import { useLiveDetection } from '../hooks/useLiveDetection.js';

export default function LiveStream({ modelId, productName, disabled = false }) {
  const { videoRef, running, defects, dimensions, error, start, stop } = useLiveDetection({
    fps: 2,
    modelId,
    productName,
  });
  const hasDimensions = dimensions.width > 0 && dimensions.height > 0;

  return (
    <div>
      <Blueprint className="qc-figure-frame">
        <div className="qc-image-stack">
          <video
            ref={videoRef}
            muted
            playsInline
            className="qc-video"
            style={hasDimensions ? { aspectRatio: dimensions.width + ' / ' + dimensions.height } : undefined}
          />
          {running && hasDimensions && (
            <DefectOverlay
              defects={defects}
              sourceWidth={dimensions.width}
              sourceHeight={dimensions.height}
            />
          )}
        </div>
        <figcaption className="qc-figcaption">
          <span className="qc-mono">
            webcam · {hasDimensions ? dimensions.width + '×' + dimensions.height : 'awaiting video'} · 2 fps
          </span>
          <span className="qc-mono">POST /api/stream</span>
        </figcaption>
      </Blueprint>
      <div className="qc-toolbar">
        {running ? (
          <button type="button" className="btn btn-secondary" onClick={stop}>Stop stream</button>
        ) : (
          <button type="button" className="btn btn-primary" disabled={disabled} onClick={start}>Start stream</button>
        )}
        <span className="qc-mono text-muted">{running ? defects.length + ' defects in frame' : 'idle'}</span>
      </div>
      {error && <p className="qc-error">{error}</p>}
    </div>
  );
}
