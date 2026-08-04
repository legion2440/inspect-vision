import { useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Download } from 'lucide-react';
import ImageUploader from '../components/ImageUploader.jsx';
import InspectionViewer from '../components/InspectionViewer.jsx';
import DefectList from '../components/DefectList.jsx';
import SeverityScore from '../components/SeverityScore.jsx';
import LiveStream from '../components/LiveStream.jsx';
import ModelSelector from '../components/ModelSelector.jsx';
import { useInspection } from '../hooks/useInspection.js';
import { annotatedImageFilename } from '../utils/media.js';
import { scoreOf } from '../utils/severity.js';

export const Route = createFileRoute('/inspect')({ component: Inspect });

function Inspect() {
  const {
    current,
    preview,
    fileMeta,
    status,
    error,
    runInspection,
    reset,
    models,
    modelsStatus,
    modelsError,
    selectedModelId,
    selectModel,
  } = useInspection();
  const [selected, setSelected] = useState(null);
  const [mode, setMode] = useState('image');

  const busy = status === 'detecting';
  const defects = current?.defects || [];
  const count = current?.totalDefects ?? defects.length;
  const viewerSrc = current?.originalImageUrl || current?.imageUrl || preview;
  const overlayDefects = current && !current.originalImageUrl ? [] : defects;
  const imageMode = mode === 'image';
  const heading = !imageMode
    ? 'Live camera inspection'
    : current
      ? 'Detection result'
      : 'Inspect an image file';

  return (
    <main className="qc-main">
      <div className="qc-pagehead">
        <div>
          <h6 className="qc-kicker">Real-time inspection</h6>
          <h1>{heading}</h1>
        </div>
        <div className="qc-toolbar">
          <div className="qc-mode-control">
            <span className="qc-mode-label" id="inspection-mode-label">Inspection mode:</span>
            <div className="seg" role="radiogroup" aria-labelledby="inspection-mode-label">
              <label className="seg-opt">
                <input
                  type="radio"
                  name="inspection-mode"
                  checked={imageMode}
                  onChange={() => setMode('image')}
                />
                Image file
              </label>
              <label className="seg-opt">
                <input
                  type="radio"
                  name="inspection-mode"
                  checked={!imageMode}
                  onChange={() => setMode('live')}
                />
                Live stream
              </label>
            </div>
          </div>
          {imageMode && current && (
            <>
              <button type="button" className="btn btn-secondary" onClick={reset}>Clear</button>
              <a
                className="btn btn-secondary"
                href={current.imageUrl}
                download={annotatedImageFilename(current.inspectionId, current.imageUrl)}
              >
                <Download size={16} strokeWidth={1.5} /> Download annotated
              </a>
            </>
          )}
        </div>
      </div>

      <ModelSelector
        models={models}
        value={selectedModelId}
        onChange={(modelId) => {
          setSelected(null);
          selectModel(modelId);
        }}
        loading={modelsStatus === 'loading'}
        error={modelsError}
      />

      {!imageMode ? (
        <div className="qc-row qc-row-inspect">
          <LiveStream modelId={selectedModelId} />
          <aside className="qc-aside">
            <p className="text-muted">
              Frames are grabbed from the camera at 2 fps and posted to <code>/api/stream</code>; the
              overlay redraws from each response.
            </p>
          </aside>
        </div>
      ) : !preview ? (
        <ImageUploader onFile={(file) => runInspection(file, selectedModelId)} error={error} />
      ) : (
        <div className="qc-row qc-row-inspect">
          <section>
            <InspectionViewer
              src={viewerSrc}
              defects={overlayDefects}
              busy={busy}
              meta={fileMeta}
              selectedIndex={selected}
            />
            <p className="text-muted qc-note">
              Boxes are drawn on a &lt;canvas&gt; over the original image. The annotated backend image
              remains available for download.
            </p>
            {error && <p className="qc-error">{error}</p>}
          </section>

          <aside className="qc-aside">
            <div className="qc-verdict">
              <div>
                <div className="qc-lab qc-lab-inv">Verdict</div>
                <div className="qc-verdict-value">{busy ? '—' : String(current?.status || '').toUpperCase()}</div>
              </div>
              <div className="qc-verdict-right">
                <div className="qc-lab qc-lab-inv">Defects</div>
                <div className="qc-verdict-value">{busy ? '—' : count}</div>
              </div>
            </div>

            {current && <SeverityScore score={scoreOf(current)} />}

            <div>
              <h6 className="qc-sectionhead">Detected defects</h6>
              {busy ? (
                <p className="qc-mono text-muted">awaiting inference…</p>
              ) : (
                <DefectList defects={defects} onSelect={setSelected} selectedIndex={selected} />
              )}
            </div>
          </aside>
        </div>
      )}
    </main>
  );
}
