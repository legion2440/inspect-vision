import { statusColor } from '../utils/colors.js';

export default function StatusTag({ status, size = 'sm' }) {
  return (
    <span
      className="tag qc-status"
      style={{
        color: statusColor(status),
        fontSize: size === 'lg' ? 13 : 11,
        padding: size === 'lg' ? '6px 14px' : '3px 10px',
      }}
    >
      {String(status || '').toUpperCase()}
    </span>
  );
}
