import Blueprint from './Blueprint.jsx';

export default function StatCell({ value, label }) {
  return (
    <Blueprint className="qc-cell">
      <span className="qc-num">{value}</span>
      <span className="qc-lab">{label}</span>
    </Blueprint>
  );
}
