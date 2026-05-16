import { useState } from 'react';
import { runConsumerAgent } from '../api';

export default function AgentPage() {
  const [task, setTask]       = useState('');
  const [budget, setBudget]   = useState('0.01');
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const handleRun = async () => {
    if (!task.trim() || task.length < 10) {
      setError('Task must be at least 10 characters.');
      return;
    }
    setError('');
    setLoading(true);
    setResult(null);
    try {
      const data = await runConsumerAgent(task, parseFloat(budget));
      setResult(data);
    } catch (e) {
      if (e.code === 'ECONNABORTED') {
        setError(
          'Request timed out. The agent may still be running — check the dashboard in a moment.'
        );
      } else {
        setError(e.response?.data?.detail || 'Agent run failed. Check the server logs.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-ink-primary mb-2">Run Consumer Agent</h1>
      <p className="text-ink-secondary text-sm mb-6">
        The agent will autonomously search the marketplace, buy relevant memory bundles
        using x402 micropayments, and generate an answer informed by purchased memories.
      </p>

      <div className="bg-surface border border-line rounded-xl p-5 mb-4">
        <label htmlFor="task-input" className="block text-sm text-ink-secondary mb-2 font-medium">
          Task
        </label>
        <textarea
          id="task-input"
          value={task}
          onChange={e => setTask(e.target.value)}
          rows={4}
          placeholder="e.g. What are the optimal LTV ratios for Aave V3 lending on WETH collateral?"
          className="w-full bg-elevated border border-line rounded-lg px-4 py-3 text-sm text-ink-primary placeholder:text-ink-muted resize-none focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
        />
        <div className="flex items-center gap-4 mt-3">
          <div className="flex items-center gap-2">
            <label htmlFor="budget-input" className="text-xs text-ink-secondary">
              Max budget (USDC)
            </label>
            <input
              id="budget-input"
              type="number"
              value={budget}
              onChange={e => setBudget(e.target.value)}
              step="0.002"
              min="0.002"
              max="0.05"
              className="w-20 bg-elevated border border-line rounded px-2 py-1 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
            />
          </div>
          <button
            onClick={handleRun}
            disabled={loading}
            className="ml-auto bg-accent hover:bg-accent-hover disabled:opacity-40 text-ink-primary px-6 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? 'Running...' : 'Run Agent'}
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="bg-danger-surface border border-danger-border rounded-lg p-3 text-sm text-danger mb-4"
        >
          {error}
        </div>
      )}

      {loading && (
        <div
          className="bg-surface border border-line rounded-xl p-8 text-center"
          role="status"
          aria-live="polite"
          aria-label="Agent is running"
        >
          <p className="text-ink-primary font-medium">Agent running...</p>
          <p className="text-ink-muted text-sm mt-1">
            Searching marketplace &rarr; evaluating bundles &rarr; paying with x402 &rarr; generating answer
          </p>
          <p className="text-ink-faint text-xs mt-3">This typically takes 5&ndash;15 seconds</p>
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="bg-surface border border-line rounded-xl p-5">
            <h2 className="text-sm font-semibold text-accent-subtle mb-3">Answer</h2>
            <p className="text-ink-primary text-sm leading-relaxed whitespace-pre-wrap">
              {result.answer}
            </p>
          </div>

          <div className="bg-surface border border-line rounded-xl p-5">
            <h2 className="text-sm font-semibold text-ink-secondary mb-3">Purchase Receipt</h2>
            <div className="grid grid-cols-3 gap-4 mb-4 text-center">
              <div>
                <div className="text-lg font-bold text-ink-primary">{result.memories_used}</div>
                <div className="text-xs text-ink-secondary">Memories used</div>
              </div>
              <div>
                <div className="text-lg font-bold text-success">
                  ${result.total_spent_usdc.toFixed(4)}
                </div>
                <div className="text-xs text-ink-secondary">USDC spent</div>
              </div>
              <div>
                <div className="text-lg font-bold text-ink-primary">
                  {result.bundles_purchased.length}
                </div>
                <div className="text-xs text-ink-secondary">Bundles purchased</div>
              </div>
            </div>

            {result.bundles_purchased.map(b => (
              <div key={b.bundle_id} className="bg-elevated rounded-lg p-3 mb-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="font-medium text-ink-primary">{b.title}</span>
                  <span className="text-success">${b.amount_usdc.toFixed(4)} USDC</span>
                </div>
                <div className="flex justify-between text-ink-muted mt-1">
                  <span>{b.memory_count} memories &middot; similarity {b.similarity.toFixed(2)}</span>
                  <span className="font-mono">{b.tx_hash.slice(0, 18)}...</span>
                </div>
              </div>
            ))}

            {result.bundles_purchased.length === 0 && (
              <p className="text-ink-muted text-xs text-center py-2">
                No bundles purchased &mdash; answer from general knowledge
              </p>
            )}
          </div>

          {result.search_queries?.length > 0 && (
            <div className="bg-surface border border-line rounded-xl p-4">
              <h2 className="text-xs font-semibold text-ink-secondary mb-2">
                Search queries generated
              </h2>
              <ul className="space-y-1">
                {result.search_queries.map((q, i) => (
                  <li key={i} className="text-xs text-ink-muted">&rsaquo; {q}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}