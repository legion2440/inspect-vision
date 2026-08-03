import { useEffect, useMemo } from 'react';
import { Link, createFileRoute, useNavigate } from '@tanstack/react-router';
import { Upload } from 'lucide-react';
import ImageUploader from '../components/ImageUploader.jsx';
import InspectionCard from '../components/InspectionCard.jsx';
import StatCell from '../components/StatCell.jsx';
import { useInspection } from '../hooks/useInspection.js';

export const Route = createFileRoute('/')({ component: Dashboard });

function Dashboard() {
  const { history, loadHistory, runInspection, error } = useInspection();
  const navigate = useNavigate();

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const stats = useMemo(() => {
    const total = history.length;
    const passed = history.filter((r) => r.status === 'passed').length;
    const defects = history.reduce((n, r) => n + (r.totalDefects ?? (r.defects || []).length), 0);
    const confs = history.flatMap((r) => (r.defects || []).map((d) => d.confidence));
    const mean = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : 0;
    return {
      total,
      passRate: total ? ((passed / total) * 100).toFixed(1) + '%' : '—',
      defects,
      mean: mean ? mean.toFixed(2) : '—',
    };
  }, [history]);

  const handleFile = async (file) => {
    navigate({ to: '/inspect' });
    await runInspection(file);
  };

  return (
    <main className="qc-main">
      <div className="qc-pagehead">
        <div>
          <h6 className="qc-kicker">Quality control / overview</h6>
          <h1>Inspection dashboard</h1>
          <p className="text-muted qc-lede">
            Live defect detection across the finishing line. Last model sync 06:00 — YOLOv8n-defect, 4 classes.
          </p>
        </div>
        <Link to="/inspect" className="btn btn-primary">
          <Upload size={16} strokeWidth={1.5} /> New inspection
        </Link>
      </div>

      <div className="qc-stats">
        <StatCell value={stats.total} label="Inspections stored" />
        <StatCell value={stats.passRate} label="Pass rate" />
        <StatCell value={stats.defects} label="Defects found" />
        <StatCell value={stats.mean} label="Mean confidence" />
      </div>

      <div className="qc-row qc-row-dash">
        <section>
          <h6 className="qc-sectionhead">Quick upload</h6>
          <ImageUploader onFile={handleFile} error={error} />
        </section>
        <section>
          <div className="qc-sectionrow">
            <h6>Recent inspections</h6>
            <Link to="/history" className="btn btn-ghost">View all</Link>
          </div>
          <div className="qc-cardlist">
            {history.slice(0, 3).map((r) => (
              <InspectionCard record={r} key={r.inspectionId} />
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
