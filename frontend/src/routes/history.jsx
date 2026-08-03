import { useEffect, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Download, Trash2 } from 'lucide-react';
import Blueprint from '../components/Blueprint.jsx';
import HistoryTable from '../components/HistoryTable.jsx';
import { useInspection } from '../hooks/useInspection.js';
import { exportHistory, usingMock } from '../utils/apiClient.js';
import { downloadBlob, downloadCsv } from '../utils/csv.js';
import { DEFECT_TYPES } from '../utils/defectTypes.js';

export const Route = createFileRoute('/history')({ component: History });

const TYPES = ['all', ...DEFECT_TYPES];

function History() {
  const { history, historyStatus, error, loadHistory, removeInspection, clearAll } = useInspection();
  const [filters, setFilters] = useState({ from: '', to: '', type: 'all', q: '' });
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    const timer = window.setTimeout(() => loadHistory(filters), filters.q ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [filters, loadHistory]);

  const rows = history;

  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));

  const handleExport = async () => {
    setActionError(null);
    try {
      if (usingMock) {
        downloadCsv(rows);
      } else {
        downloadBlob(await exportHistory(filters));
      }
    } catch (err) {
      setActionError(err.message || 'Could not export inspection history');
    }
  };

  const handleDelete = async (id) => {
    setActionError(null);
    try {
      await removeInspection(id);
    } catch (err) {
      setActionError(err.message || 'Could not delete inspection');
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Clear all inspection history?')) return;
    setActionError(null);
    try {
      await clearAll();
    } catch (err) {
      setActionError(err.message || 'Could not clear inspection history');
    }
  };

  return (
    <main className="qc-main">
      <div className="qc-pagehead">
        <div>
          <h6 className="qc-kicker">Inspection history</h6>
          <h1>{rows.length} records</h1>
        </div>
        <div className="qc-toolbar">
          <button type="button" className="btn btn-secondary" onClick={handleExport}>
            <Download size={16} strokeWidth={1.5} /> Export CSV
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleClear}
          >
            <Trash2 size={16} strokeWidth={1.5} /> Clear history
          </button>
        </div>
      </div>

      <Blueprint className="qc-filters">
        <div className="field">
          <label htmlFor="from">From</label>
          <input id="from" className="input" type="date" value={filters.from} onChange={set('from')} />
        </div>
        <div className="field">
          <label htmlFor="to">To</label>
          <input id="to" className="input" type="date" value={filters.to} onChange={set('to')} />
        </div>
        <div className="field">
          <label htmlFor="type">Defect type</label>
          <select id="type" className="input" value={filters.type} onChange={set('type')}>
            {TYPES.map((t) => (
              <option value={t} key={t}>{t === 'all' ? 'All types' : t}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="q">Search</label>
          <input
            id="q"
            className="input"
            placeholder="Inspection ID or file name"
            value={filters.q}
            onChange={set('q')}
          />
        </div>
      </Blueprint>

      {historyStatus === 'error' && error && <p className="qc-error">{error}</p>}
      {actionError && <p className="qc-error">{actionError}</p>}
      <HistoryTable records={rows} onDelete={handleDelete} loading={historyStatus === 'loading'} />
    </main>
  );
}
