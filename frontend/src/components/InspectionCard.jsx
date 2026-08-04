import { Link } from '@tanstack/react-router';
import Blueprint from './Blueprint.jsx';
import StatusTag from './StatusTag.jsx';
import { modelLabel, stamp } from '../utils/format.js';
import { scoreOf } from '../utils/severity.js';

export default function InspectionCard({ record }) {
  const count = record.totalDefects ?? (record.defects || []).length;
  return (
    <Blueprint className="qc-inspection-card">
      <Link to="/details/$id" params={{ id: record.inspectionId }} className="qc-card-link">
        <span className="qc-mono qc-card-id">{record.inspectionId}</span>
        <span className="qc-card-title">
          {count ? count + ' defects · ' + record.defects[0].type : 'No defects detected'}
        </span>
        <span className="qc-lab">
          {stamp(record.timestamp)} · {modelLabel(record)} · score {scoreOf(record)}
        </span>
      </Link>
      <StatusTag status={record.status} />
    </Blueprint>
  );
}
