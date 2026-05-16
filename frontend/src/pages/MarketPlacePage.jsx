import { useEffect, useState, useCallback } from 'react';
import { getMarketplace, getPlatformStats } from '../api';

const PAGE_SIZE = 20;

export default function MarketplacePage() {
  const [listings, setListings]       = useState([]);
  const [stats, setStats]             = useState(null);
  const [sort, setSort]               = useState('top_rated');
  const [loading, setLoading]         = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError]             = useState('');
  const [offset, setOffset]           = useState(0);
  const [hasMore, setHasMore]         = useState(true);

  const fetchListings = useCallback((currentSort, currentOffset, append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setError('');
    }

    const requests = append
      ? [getMarketplace(currentSort, PAGE_SIZE, currentOffset)]
      : [getMarketplace(currentSort, PAGE_SIZE, 0), getPlatformStats()];

    Promise.all(requests)
      .then(results => {
        if (append) {
          const [newListings] = results;
          setListings(prev => [...prev, ...newListings]);
          setHasMore(newListings.length === PAGE_SIZE);
        } else {
          const [newListings, newStats] = results;
          setListings(newListings);
          setStats(newStats);
          setHasMore(newListings.length === PAGE_SIZE);
          setOffset(0);
        }
      })
      .catch(() =>
        setError('Failed to load marketplace. Check your connection and try again.')
      )
      .finally(() => {
        setLoading(false);
        setLoadingMore(false);
      });
  }, []);

  useEffect(() => {
    fetchListings(sort, 0, false);
  }, [sort, fetchListings]);

  const handleLoadMore = () => {
    const nextOffset = offset + PAGE_SIZE;
    setOffset(nextOffset);
    fetchListings(sort, nextOffset, true);
  };

  const SORT_OPTIONS = ['top_rated', 'popular', 'newest', 'cheapest'];

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Bundles',       value: stats.total_bundles },
            { label: 'Purchases',     value: stats.total_purchases },
            { label: 'Volume (USDC)', value: `$${stats.total_volume_usdc.toFixed(4)}` },
            { label: 'Publishers',    value: stats.unique_publishers },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="bg-surface rounded-xl p-4 text-center border border-line"
            >
              <div className="text-2xl font-bold text-accent-subtle">{value}</div>
              <div className="text-sm text-ink-secondary mt-1">{label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <span className="text-ink-secondary text-sm">Sort by:</span>
        {SORT_OPTIONS.map(s => (
          <button
            key={s}
            onClick={() => setSort(s)}
            aria-pressed={sort === s}
            className={`px-3 py-1 rounded-full text-sm transition-colors ${
              sort === s
                ? 'bg-accent text-ink-primary'
                : 'bg-elevated text-ink-secondary hover:bg-line-strong'
            }`}
          >
            {s.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {error && (
        <div
          role="alert"
          className="bg-danger-surface border border-danger-border rounded-lg p-4 text-sm text-danger mb-6"
        >
          {error}
        </div>
      )}

      {loading ? (
        <div
          className="text-center text-ink-muted py-20"
          role="status"
          aria-live="polite"
        >
          Loading marketplace...
        </div>
      ) : listings.length === 0 && !error ? (
        <div className="text-center text-ink-muted py-20">
          No bundles found. Be the first to publish one.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {listings.map(bundle => (
              <BundleCard key={bundle.bundle_id} bundle={bundle} />
            ))}
          </div>

          {hasMore && (
            <div className="text-center mt-8">
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="bg-elevated hover:bg-line-strong disabled:opacity-40 text-ink-secondary px-6 py-2 rounded-lg text-sm transition-colors"
              >
                {loadingMore ? 'Loading...' : 'Load more'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function BundleCard({ bundle }) {
  return (
    <article className="bg-surface border border-line rounded-xl p-5 hover:border-line-strong transition-colors">
      <div className="flex items-start justify-between mb-3">
        <h3 className="font-semibold text-ink-primary text-sm leading-snug flex-1 mr-2">
          {bundle.title}
        </h3>
        <span
          className="text-accent-subtle font-bold text-sm whitespace-nowrap"
          aria-label={`Price: $${bundle.price_usdc.toFixed(4)} USDC`}
        >
          ${bundle.price_usdc.toFixed(4)}
        </span>
      </div>

      <p className="text-ink-secondary text-xs mb-4 line-clamp-2">{bundle.description}</p>

      <div className="flex items-center justify-between text-xs text-ink-muted">
        <span>Quality: {(bundle.avg_quality_score * 5).toFixed(1)}/5</span>
        <span>{bundle.memory_count} memories</span>
        <span>{bundle.purchase_count} sold</span>
      </div>

      {bundle.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3" aria-label="Tags">
          {bundle.tags.slice(0, 3).map(tag => (
            <span
              key={tag}
              className="bg-elevated text-ink-secondary text-xs px-2 py-0.5 rounded-full"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div
        className="mt-3 text-xs text-ink-faint font-mono truncate"
        aria-label="Publisher wallet"
      >
        {bundle.publisher_wallet.slice(0, 16)}...
      </div>
    </article>
  );
}