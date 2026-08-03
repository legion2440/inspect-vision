import { Link, Outlet, createRootRoute } from '@tanstack/react-router';
import { usingMock } from '../utils/apiClient.js';

export const Route = createRootRoute({
  component: RootLayout,
  notFoundComponent: () => (
    <main className="qc-main">
      <h1>Route not found</h1>
      <Link to="/" className="btn btn-secondary">Back to dashboard</Link>
    </main>
  ),
});

function RootLayout() {
  return (
    <div className="qc-app">
      <header className="nav qc-nav">
        <div className="nav-brand qc-brand">
          <span>INSPECT·VISION</span>
          <span className="qc-mono qc-brand-ver">v1.0</span>
        </div>
        <nav className="qc-navlinks">
          <Link to="/" activeOptions={{ exact: true }} className="qc-navlink">Dashboard</Link>
          <Link to="/inspect" className="qc-navlink">Inspect</Link>
          <Link to="/history" className="qc-navlink">History</Link>
        </nav>
        <div className="qc-line">
          <span className="qc-dot" />
          <span className="qc-mono">LINE 04 · SHIFT B{usingMock ? ' · MOCK API' : ''}</span>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
