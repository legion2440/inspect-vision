// Functional status colors — muted so they sit inside the steel palette.
export const OK = '#4d7a5f';
export const WARN = '#9c7d3c';
export const BAD = '#a1554d';

/** Confidence coding required by the spec: >90% green, 70-90% yellow, <70% red. */
export const confidenceColor = (c) => (c > 0.9 ? OK : c >= 0.7 ? WARN : BAD);

export const scoreColor = (s) => (s >= 85 ? OK : s >= 60 ? WARN : BAD);

export const statusColor = (status) => (status === 'passed' ? OK : BAD);
