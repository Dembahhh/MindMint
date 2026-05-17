import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import MarketplacePage from './pages/MarketPlacePage';
import AgentPage from './pages/AgentPage';
import DashboardPage from './pages/DashboardPage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className="min-h-screen bg-base text-ink-primary">
          <nav
            aria-label="Main navigation"
            className="border-b border-line px-6 py-4 flex items-center gap-8"
          >
            <span className="text-xl font-bold text-accent-subtle">
              <span aria-hidden="true">🧠 </span>MindMint
            </span>
            {[
              { to: '/', label: 'Marketplace', end: true },
              { to: '/agent', label: 'Run Agent' },
              { to: '/dashboard', label: 'Dashboard' },
            ].map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  isActive
                    ? 'text-accent-subtle font-medium'
                    : 'text-ink-secondary hover:text-ink-primary transition-colors'
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          <main>
            <Routes>
              <Route path="/"          element={<MarketplacePage />} />
              <Route path="/agent"     element={<AgentPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="*"          element={<NotFoundPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
}