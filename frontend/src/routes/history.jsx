import { useEffect, useMemo, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Download, Trash2 } from 'lucide-react';
import Blueprint from '../components/Blueprint.jsx';
import HistoryTable from '../components/HistoryTable.jsx';
import { useInspection } from '../hooks/useInspection.js';
import { downloadCsv } from '../utils/csv.js';
import { dayOf, defectTypes } from '../utils/format.js';

export const Route = createFileRoute('/history')({ component: History });

const TYPES = ['all', 'scratch', 'dent', 'crack', 'discoloration'];

function History() {
  const { history, historyStatus, loadHistory, removeInspection, clearAll } = useInspection();
  const [filters, setFilters] = useState({ from: '', to: '', type: 'all', q: '' });

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // Server-side filtering is supported through /api/history; this keeps the
  // table responsive while typing and works against the mock API too.
  const rows = useMemo(
    () =>
      history.filter((r) => {
        const day = dayOf(r.timestamp);
        if (filters.from && day < filters.from) return false;
        if (filters.to && day > filters.to) return false;
        if (filters.type !== 'all' && !defectTypes(r).includes(filters.type)) return false;
        if (filters.q) {
          const hay = (r.inspectionId + ' ' + (r.fileName || '')).toLowerCase();
          if (!hay.includes(filters.q.toLowerCase())) return false;
        }
        return true;
      }),
    [history, filters],
  );

  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));

  return (
    <main className="qc-main">
      <div className="qc-pagehead">
        <div>
          <h6 className="qc-kicker">Inspection history</h6>
          <h1>{rows.length} records</h1>
        </div>
        <div className="qc-toolbar">
          <button type="button" className="btn btn-secondary" onClick={() => downloadCsv(rows)}>
            <Download size={16} strokeWidth={1.5} /> Export CSV
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => window.confirm('Clear all inspection history?') && clearAll()}
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

      <HistoryTable records={rows} onDelete={removeInspection} loading={historyStatus === 'loading'} />
    </main>
  );
}
