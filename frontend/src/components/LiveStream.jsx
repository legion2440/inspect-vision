import Blueprint from './Blueprint.jsx';
import DefectOverlay from './DefectOverlay.jsx';
import { useLiveDetection } from '../hooks/useLiveDetection.js';

/** Bonus: webcam capture with per-frame detections from /api/stream. */
export default function LiveStream() {
  const { videoRef, running, defects, error, start, stop } = useLiveDetection({ fps: 2 });

  return (
    <div>
      <Blueprint className="qc-figure-frame">
        <div className="qc-image-stack">
          <video ref={videoRef} muted playsInline className="qc-video" />
          {running && <DefectOverlay defects={defects} sourceWidth={1280} sourceHeight={720} />}
        </div>
        <figcaption className="qc-figcaption">
          <span className="qc-mono">webcam · 1280×720 · 2 fps</span>
          <span className="qc-mono">POST /api/stream</span>
        </figcaption>
      </Blueprint>
      <div className="qc-toolbar">
        {running ? (
          <button type="button" className="btn btn-secondary" onClick={stop}>Stop stream</button>
        ) : (
          <button type="button" className="btn btn-primary" onClick={start}>Start stream</button>
        )}
        <span className="qc-mono text-muted">{running ? defects.length + ' defects in frame' : 'idle'}</span>
      </div>
      {error && <p className="qc-error">{error}</p>}
    </div>
  );
}
