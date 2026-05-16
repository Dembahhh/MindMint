import { useEffect, useState } from 'react';
import { getLeaderboard, getPublisherDashboard } from '../api';

const ETH_ADDRESS_REGEX = /^0x[0-9a-fA-F]{40}$/;

export default function DashboardPage() {
  const [leaderboard, setLeaderboard] = useState([]);
  const [wallet, setWallet]           = useState('');
  const [dashboard, setDashboard]     = useState(null);
  const [dashError, setDashError]     = useState('');
  const [loading, setLoading]         = useState(false);

  useEffect(() => {
    getLeaderboard(10).then(setLeaderboard).catch(console.error);
  }, []);

  const handleLookup = async (addressOverride) => {
    const address = (addressOverride || wallet).trim();
    if (!address) return;
    if (!ETH_ADDRESS_REGEX.test(address)) {
      setDashError('Enter a valid Ethereum address (0x followed by 40 hex characters).');
      return;
    }
    setDashError('');
    setLoading(true);
    setDashboard(null);
    try {
      const data = await getPublisherDashboard(address);
      setDashboard(data);
    } catch (e) {
      setDashError(
        e.response?.status === 404
          ? 'No data found for this wallet.'
          : 'Lookup failed. Check the wallet address and try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRowClick = (publisherWallet) => {
    setWallet(publisherWallet);
    handleLookup(publisherWallet);
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
      <section aria-labelledby="leaderboard-heading">
        <h2 id="leaderboard-heading" className="text-xl font-bold text-ink-primary mb-4">
          Publisher Leaderboard
        </h2>
        <div className="bg-surface border border-line rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-elevated text-ink-secondary text-xs">
              <tr>
                {['Rank', 'Wallet', 'Bundles', 'Sales', 'Earned (USDC)', 'Avg Quality'].map(
                  (col, i) => (
                    <th
                      key={col}
                      scope="col"
                      className={`px-4 py-3 ${i > 1 ? 'text-right' : 'text-left'}`}
                    >
                      {col}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {leaderboard.map(e => (
                <tr
                  key={e.publisher_wallet}
                  className="border-t border-line hover:bg-elevated cursor-pointer transition-colors"
                  onClick={() => handleRowClick(e.publisher_wallet)}
                  title="Click to view publisher dashboard"
                >
                  <td className="px-4 py-3 text-ink-secondary">#{e.rank}</td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-primary">
                    {e.publisher_wallet.slice(0, 18)}...
                  </td>
                  <td className="px-4 py-3 text-right text-ink-primary">{e.bundle_count}</td>
                  <td className="px-4 py-3 text-right text-ink-primary">{e.total_purchase_count}</td>
                  <td className="px-4 py-3 text-right text-success font-medium">
                    ${e.total_earned_usdc.toFixed(6)}
                  </td>
                  <td className="px-4 py-3 text-right text-accent-subtle">
                    {(e.avg_quality_score * 5).toFixed(1)}/5
                  </td>
                </tr>
              ))}
              {leaderboard.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-muted">
                    No publishers yet. Publish a memory bundle to appear here.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {leaderboard.length > 0 && (
          <p className="text-xs text-ink-faint mt-2">
            Click a row to view that publisher&apos;s earnings below.
          </p>
        )}
      </section>

      <section aria-labelledby="earnings-heading">
        <h2 id="earnings-heading" className="text-xl font-bold text-ink-primary mb-4">
          Publisher Earnings
        </h2>
        <div className="flex gap-3 mb-4">
          <label htmlFor="wallet-input" className="sr-only">
            Publisher wallet address
          </label>
          <input
            id="wallet-input"
            value={wallet}
            onChange={e => setWallet(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleLookup()}
            placeholder="0x... publisher wallet address"
            className="flex-1 bg-surface border border-line rounded-lg px-4 py-2 text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
          />
          <button
            onClick={() => handleLookup()}
            disabled={loading}
            className="bg-accent hover:bg-accent-hover disabled:opacity-40 text-ink-primary px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? 'Loading...' : 'Look up'}
          </button>
        </div>

        {dashError && (
          <p role="alert" className="text-danger text-sm mb-4">{dashError}</p>
        )}

        {dashboard && (
          <div className="bg-surface border border-line rounded-xl p-5">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                { label: 'Bundles',       value: dashboard.bundle_count },
                { label: 'Total Sales',   value: dashboard.total_purchase_count },
                { label: 'Earned (USDC)', value: `$${dashboard.total_earned_usdc.toFixed(6)}` },
                { label: 'Avg Quality',   value: `${(dashboard.avg_quality_score * 5).toFixed(1)}/5` },
              ].map(({ label, value }) => (
                <div key={label} className="text-center">
                  <div className="text-xl font-bold text-accent-subtle">{value}</div>
                  <div className="text-xs text-ink-secondary mt-1">{label}</div>
                </div>
              ))}
            </div>

            <h3 className="text-sm font-semibold text-ink-secondary mb-3">Top Bundles</h3>
            <div className="space-y-2">
              {dashboard.top_bundles.map(b => (
                <div
                  key={b.bundle_id}
                  className="flex justify-between items-center bg-elevated rounded-lg px-4 py-3 text-sm"
                >
                  <span className="text-ink-primary">{b.title}</span>
                  <div className="flex gap-4 text-xs text-ink-secondary">
                    <span>{b.purchase_count} sales</span>
                    <span className="text-success">${b.total_earned_usdc.toFixed(6)} USDC</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}