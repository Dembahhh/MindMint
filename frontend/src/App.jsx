import { BrowserRouter, Routes, Route, NavLink, Link } from "react-router-dom";
import { useEffect } from "react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import LandingPage from "./pages/LandingPage";
import MarketplacePage from "./pages/MarketPlacePage";
import AgentPage from "./pages/AgentPage";
import DashboardPage from "./pages/DashboardPage";
import NotFoundPage from "./pages/NotFoundPage";
import { getHealth } from "./api";


function useBackendWakeup() {
  useEffect(() => {
    getHealth().catch(() => {});
  }, []);
}

const NAV_LINKS = [
  { to: "/marketplace", label: "Marketplace" },
  { to: "/agent", label: "Run Agent" },
  { to: "/dashboard", label: "Dashboard" },
];

export default function App() {
  useBackendWakeup();

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className="min-h-screen bg-base text-ink-primary">
          <nav
            aria-label="Main navigation"
            className="border-b border-line px-6 py-4 flex items-center gap-8"
          >
            <Link
              to="/"
              className="text-xl font-bold text-accent-subtle hover:opacity-80
                         transition-opacity focus:outline-none focus:ring-2
                         focus:ring-accent rounded"
              aria-label="MindMint — go to home"
            >
              <span aria-hidden="true"> </span>MindMint
            </Link>

            {NAV_LINKS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  isActive
                    ? "text-accent-subtle font-medium"
                    : "text-ink-secondary hover:text-ink-primary transition-colors"
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          <main>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/marketplace" element={<MarketplacePage />} />
              <Route path="/agent" element={<AgentPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
