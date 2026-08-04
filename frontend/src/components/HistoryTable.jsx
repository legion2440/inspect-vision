import { Link } from '@tanstack/react-router';
import StatusTag from './StatusTag.jsx';
import { defectTypes, modelLabel, stamp } from '../utils/format.js';
import { scoreOf } from '../utils/severity.js';

export default function HistoryTable({ records = [], onDelete, loading }) {
  if (loading) return <p className="qc-mono text-muted">Loading history…</p>;
  if (!records.length) return <p className="qc-mono text-muted">No inspections match these filters.</p>;

  return (
    <div className="qc-table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: 190 }}>Inspection</th>
            <th style={{ width: 170 }}>Timestamp</th>
            <th style={{ width: 190 }}>Model</th>
            <th style={{ width: 80 }}>Defects</th>
            <th>Types</th>
            <th style={{ width: 90 }}>Score</th>
            <th style={{ width: 100 }}>Status</th>
            <th style={{ width: 120 }} aria-label="actions" />
          </tr>
        </thead>
        <tbody>
          {records.map((r) => {
            const types = defectTypes(r);
            const modelId = r.model?.id;
            const displayName = modelLabel(r);
            return (
              <tr key={r.inspectionId}>
                <td className="qc-mono qc-accent">{r.inspectionId}</td>
                <td className="qc-mono">{stamp(r.timestamp)}</td>
                <td>
                  <span className="qc-model-cell">
                    <span>{displayName}</span>
                    {modelId && modelId !== displayName && (
                      <span className="qc-mono qc-model-id">{modelId}</span>
                    )}
                  </span>
                </td>
                <td>{r.totalDefects ?? (r.defects || []).length}</td>
                <td>
                  <span className="qc-tags">
                    {(types.length ? types : ['none']).map((t) => (
                      <span className="tag tag-accent" key={t}>{t}</span>
                    ))}
                  </span>
                </td>
                <td className="qc-mono">{scoreOf(r)}</td>
                <td><StatusTag status={r.status} /></td>
                <td>
                  <span className="qc-actions">
                    <Link to="/details/$id" params={{ id: r.inspectionId }} className="btn btn-ghost">View</Link>
                    <button type="button" className="btn btn-ghost qc-danger" onClick={() => onDelete(r.inspectionId)}>
                      Delete
                    </button>
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
