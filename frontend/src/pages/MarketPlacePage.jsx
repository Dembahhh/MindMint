import { useEffect, useState, useCallback, useRef } from "react";
import { getMarketplace, getPlatformStats } from "../api";

const PAGE_SIZE = 20;
const RETRY_DELAY = 20; 
const SKELETON_COUNT = 6;


function SkeletonCard() {
  return (
    <div
      className="bg-surface border border-line rounded-xl p-5 animate-pulse"
      aria-hidden="true"
    >
      <div className="flex justify-between mb-3">
        <div className="h-4 bg-elevated rounded w-3/4" />
        <div className="h-4 bg-elevated rounded w-12" />
      </div>
      <div className="h-3 bg-elevated rounded w-full mb-2" />
      <div className="h-3 bg-elevated rounded w-2/3 mb-4" />
      <div className="flex justify-between gap-2">
        <div className="h-3 bg-elevated rounded w-20" />
        <div className="h-3 bg-elevated rounded w-16" />
        <div className="h-3 bg-elevated rounded w-14" />
      </div>
      <div className="flex gap-1 mt-3">
        <div className="h-5 bg-elevated rounded-full w-14" />
        <div className="h-5 bg-elevated rounded-full w-10" />
      </div>
    </div>
  );
}

function StatsSkeleton() {
  return (
    <div
      className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8"
      aria-hidden="true"
    >
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="bg-surface rounded-xl p-4 text-center border border-line animate-pulse"
        >
          <div className="h-8 bg-elevated rounded w-16 mx-auto mb-2" />
          <div className="h-3 bg-elevated rounded w-20 mx-auto" />
        </div>
      ))}
    </div>
  );
}

function BundleCard({ bundle }) {
  return (
    <article
      className="bg-surface border border-line rounded-xl p-5
                 hover:border-line-strong transition-colors"
    >
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

      <p className="text-ink-secondary text-xs mb-4 line-clamp-2">
        {bundle.description}
      </p>

      <div className="flex items-center justify-between text-xs text-ink-muted">
        <span>Quality: {(bundle.avg_quality_score * 5).toFixed(1)}/5</span>
        <span>{bundle.memory_count} memories</span>
        <span>{bundle.purchase_count} sold</span>
      </div>

      {bundle.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3" aria-label="Tags">
          {bundle.tags.slice(0, 3).map((tag) => (
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

const SORT_OPTIONS = ["top_rated", "popular", "newest", "cheapest"];

export default function MarketplacePage() {
  const [listings, setListings] = useState([]);
  const [stats, setStats] = useState(null);
  const [sort, setSort] = useState("top_rated");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const countdownRef = useRef(null);

  const runCountdown = useCallback(() => {
    return new Promise((resolve) => {
      let remaining = RETRY_DELAY;
      setCountdown(remaining);

      countdownRef.current = setInterval(() => {
        remaining -= 1;
        setCountdown(remaining);
        if (remaining <= 0) {
          clearInterval(countdownRef.current);
          resolve();
        }
      }, 1000);
    });
  }, []);

  const fetchListings = useCallback(
    async (currentSort, currentOffset, append = false) => {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setError("");
      }

      const doFetch = () => {
        const requests = append
          ? [getMarketplace(currentSort, PAGE_SIZE, currentOffset)]
          : [getMarketplace(currentSort, PAGE_SIZE, 0), getPlatformStats()];
        return Promise.all(requests);
      };

      try {
        let results;

        try {
          // ── First attempt ──────────────────────────────────────
          results = await doFetch();
        } catch {
          // ── Backend sleeping — wait, then retry once ───────────
          // Only show the retry UI for full-page loads, not "load more"
          if (!append) {
            setRetrying(true);
            await runCountdown();
            setRetrying(false);
          }
          // Second attempt — if this throws, the outer catch handles it
          results = await doFetch();
        }

        // ── Success ─────────────────────────────────────────────
        if (append) {
          const [newListings] = results;
          setListings((prev) => [...prev, ...newListings]);
          setHasMore(newListings.length === PAGE_SIZE);
        } else {
          const [newListings, newStats] = results;
          setListings(newListings);
          setStats(newStats);
          setHasMore(newListings.length === PAGE_SIZE);
          setOffset(0);
        }
      } catch {
        setError(
          "Failed to load marketplace. Check your connection and try again.",
        );
      } finally {
        setLoading(false);
        setLoadingMore(false);
        setRetrying(false);
        setCountdown(0);
      }
    },
    [runCountdown],
  );

  useEffect(() => {
    fetchListings(sort, 0, false);
  }, [sort, fetchListings]);

  useEffect(() => {
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  const handleLoadMore = () => {
    const nextOffset = offset + PAGE_SIZE;
    setOffset(nextOffset);
    fetchListings(sort, nextOffset, true);
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Bundles", value: stats.total_bundles },
            { label: "Purchases", value: stats.total_purchases },
            {
              label: "Volume (USDC)",
              value: `$${stats.total_volume_usdc.toFixed(4)}`,
            },
            { label: "Publishers", value: stats.unique_publishers },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="bg-surface rounded-xl p-4 text-center border border-line"
            >
              <div className="text-2xl font-bold text-accent-subtle">
                {value}
              </div>
              <div className="text-sm text-ink-secondary mt-1">{label}</div>
            </div>
          ))}
        </div>
      ) : loading ? (
        <StatsSkeleton />
      ) : null}

      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <span className="text-ink-secondary text-sm">Sort by:</span>
        {SORT_OPTIONS.map((s) => (
          <button
            key={s}
            onClick={() => setSort(s)}
            aria-pressed={sort === s}
            className={`px-3 py-1 rounded-full text-sm transition-colors ${
              sort === s
                ? "bg-accent text-ink-primary"
                : "bg-elevated text-ink-secondary hover:bg-line-strong"
            }`}
          >
            {s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {retrying && (
        <div
          role="status"
          aria-live="polite"
          className="bg-elevated border border-line rounded-lg p-4 text-sm
                     text-ink-secondary mb-6 flex items-center gap-3"
        >
          <span
            className="w-2 h-2 rounded-full bg-accent-subtle animate-pulse flex-shrink-0"
            aria-hidden="true"
          />
          <span>
            Server is waking up — this takes about {RETRY_DELAY} seconds on
            first load. Retrying in{" "}
            <strong className="text-ink-primary">{countdown}s</strong>…
          </span>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="bg-danger-surface border border-danger-border rounded-lg p-4
                     text-sm text-danger mb-6"
        >
          {error}
        </div>
      )}

      {loading ? (
        <>
          <div className="sr-only" role="status" aria-live="polite">
            {retrying
              ? `Server waking up, retrying in ${countdown} seconds`
              : "Loading marketplace listings"}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </>
      ) : listings.length === 0 && !error ? (
        <div className="text-center text-ink-muted py-20">
          No bundles found. Be the first to publish one.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {listings.map((bundle) => (
              <BundleCard key={bundle.bundle_id} bundle={bundle} />
            ))}
          </div>

          {hasMore && (
            <div className="text-center mt-8">
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="bg-elevated hover:bg-line-strong disabled:opacity-40
                           text-ink-secondary px-6 py-2 rounded-lg text-sm
                           transition-colors"
              >
                {loadingMore ? "Loading…" : "Load more"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
