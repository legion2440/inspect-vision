import { useEffect, useState } from 'react';
import { Link, createFileRoute } from '@tanstack/react-router';
import { Download } from 'lucide-react';
import Blueprint from '../components/Blueprint.jsx';
import InspectionViewer from '../components/InspectionViewer.jsx';
import StatusTag from '../components/StatusTag.jsx';
import { deleteInspection, getInspection } from '../utils/apiClient.js';
import { confidenceColor } from '../utils/colors.js';
import { boxLabel, pct, stamp } from '../utils/format.js';
import { scoreOf } from '../utils/severity.js';

export const Route = createFileRoute('/details/$id')({ component: Details });

function Details() {
  const { id } = Route.useParams();
  const navigate = Route.useNavigate();
  const [record, setRecord] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    getInspection(id)
      .then((r) => alive && setRecord(r))
      .catch((e) => alive && setError(e.message || 'Inspection not found'));
    return () => { alive = false; };
  }, [id]);

  if (error) {
    return (
      <main className="qc-main">
        <h1>{error}</h1>
        <Link to="/history" className="btn btn-secondary">Back to history</Link>
      </main>
    );
  }
  if (!record) return <main className="qc-main"><p className="qc-mono text-muted">Loading record…</p></main>;

  const defects = record.defects || [];
  const viewerSrc = record.originalImageUrl || record.imageUrl;
  const overlayDefects = record.originalImageUrl ? defects : [];

  return (
    <main className="qc-main">
      <Link to="/history" className="btn btn-ghost qc-back">← Back to history</Link>

      <div className="qc-pagehead">
        <div>
          <h6 className="qc-kicker">Inspection record</h6>
          <h1 className="qc-mono-title">{record.inspectionId}</h1>
        </div>
        <StatusTag status={record.status} size="lg" />
      </div>

      <div className="qc-metagrid">
        <div className="qc-cell"><span className="qc-lab">Timestamp</span><span className="qc-mono">{stamp(record.timestamp)}</span></div>
        <div className="qc-cell"><span className="qc-lab">Source file</span><span className="qc-mono">{record.fileName || '—'}</span></div>
        <div className="qc-cell"><span className="qc-lab">Total defects</span><span className="qc-mono">{record.totalDefects ?? defects.length}</span></div>
        <div className="qc-cell"><span className="qc-lab">Severity score</span><span className="qc-mono">{scoreOf(record)} / 100</span></div>
      </div>

      <div className="qc-row qc-row-details">
        <InspectionViewer
          src={viewerSrc}
          defects={overlayDefects}
          meta={{ name: record.fileName }}
          caption="original image with interactive canvas overlay"
        />
        <div>
          <h6 className="qc-sectionhead">Defect breakdown</h6>
          <table className="table">
            <thead><tr><th>Type</th><th>Conf.</th><th>Box (x, y, w, h)</th></tr></thead>
            <tbody>
              {defects.length === 0 && <tr><td colSpan={3} className="text-muted">No defects recorded.</td></tr>}
              {defects.map((d, i) => (
                <tr key={i}>
                  <td className="qc-capitalize">{d.type}</td>
                  <td className="qc-mono" style={{ color: confidenceColor(d.confidence) }}>{pct(d.confidence)}</td>
                  <td className="qc-mono">{boxLabel(d.boundingBox)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="qc-toolbar qc-toolbar-lg">
            <a className="btn btn-primary" href={record.imageUrl} download={record.inspectionId + '.jpg'}>
              <Download size={16} strokeWidth={1.5} /> Download annotated
            </a>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={async () => { await deleteInspection(record.inspectionId); navigate({ to: '/history' }); }}
            >
              Delete record
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
