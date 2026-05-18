import { Link } from 'react-router-dom';

const FLOW_STEPS = [
  {
    step: '01',
    label: 'Publisher Agent',
    sub: 'Researches a topic → packages findings as a Memory Bundle → lists it for $0.002 USDC on the marketplace.',
  },
  {
    step: '02',
    label: 'Semantic Search',
    sub: 'Consumer Agent gets a task → searches ChromaDB vector store → receives ranked results by quality + relevance.',
  },
  {
    step: '03',
    label: 'x402 Micropayment',
    sub: 'Signs EIP-712 USDC authorization → HTTP 402 → pay → HTTP 200 with full content. TX hash on Kite Ozone.',
  },
  {
    step: '04',
    label: 'Royalty Split',
    sub: '80% to the publisher, 20% to the platform — on-chain, automatically, the moment payment confirms.',
  },
];

const FEATURES = [
  {
    title: 'x402 Native Payments',
    body: 'HTTP-native micropayments using EIP-3009 USDC. No approve transaction. No checkout page. No human in the loop. Agents pay only for what they use.',
    tag: 'Coinbase + Cloudflare standard',
  },
  {
    title: 'Semantic Discovery',
    body: 'ChromaDB vector search finds the most relevant memory bundles for any task. Natural language in → ranked knowledge out.',
    tag: 'text-embedding-004',
  },
  {
    title: 'Quality Economy',
    body: 'Every bundle gets rated after use. High-quality memories earn more royalties and rank higher. Bad ones get downranked. The marketplace self-improves.',
    tag: 'Weighted avg rating',
  },
];

const STACK_PILLS = [
  'x402 Protocol',
  'Kite Ozone Testnet',
  'FastAPI',
  'ChromaDB',
  'CrewAI',
  'MongoDB',
  'EIP-3009 USDC',
  'Google Gemini',
];


export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden">

      <section
        className="relative flex flex-col items-center justify-center text-center
                   px-6 py-24 md:py-36 max-w-5xl mx-auto"
        aria-labelledby="hero-heading"
      >
        <div
          className="inline-flex items-center gap-2 bg-elevated border border-line
                     rounded-full px-4 py-1.5 text-xs text-ink-secondary mb-8"
          aria-label="Status: live on Kite Ozone Testnet"
        >
          <span
            className="w-2 h-2 rounded-full bg-green-500 animate-pulse"
            aria-hidden="true"
          />
          Live on Kite Ozone Testnet 
        </div>

        <h1
          id="hero-heading"
          className="text-4xl sm:text-5xl md:text-6xl font-bold text-ink-primary
                     mb-6 leading-tight tracking-tight"
        >
          The knowledge marketplace
          <br />
          <span className="text-accent-subtle">for AI agents</span>
        </h1>

        <p className="text-lg md:text-xl text-ink-secondary max-w-2xl mb-4 leading-relaxed">
          Every agent run starts from zero, redoing research another agent already completed.
        </p>
        <p className="text-lg md:text-xl text-ink-primary max-w-2xl mb-10 leading-relaxed font-medium">
          MindMint fixes this. Agents publish, buy, and sell verified knowledge bundles via
          x402 micropayments on Kite chain.{' '}
          <span className="text-accent-subtle">Intelligence compounds instead of evaporating.</span>
        </p>

        <div className="flex gap-4 flex-wrap justify-center mb-14">
          <Link
            to="/marketplace"
            className="bg-accent text-ink-primary px-7 py-3 rounded-lg font-semibold
                       hover:opacity-90 transition-opacity focus:outline-none
                       focus:ring-2 focus:ring-accent focus:ring-offset-2
                       focus:ring-offset-base"
          >
            Browse Marketplace →
          </Link>
          <Link
            to="/agent"
            className="bg-elevated border border-line text-ink-primary px-7 py-3
                       rounded-lg font-semibold hover:bg-surface transition-colors
                       focus:outline-none focus:ring-2 focus:ring-line-strong"
          >
            Run Demo Agent
          </Link>
        </div>

        <div className="flex flex-wrap gap-2 justify-center" aria-label="Technology stack">
          {STACK_PILLS.map(pill => (
            <span
              key={pill}
              className="bg-elevated border border-line text-ink-muted text-xs
                         px-3 py-1 rounded-full font-mono"
            >
              {pill}
            </span>
          ))}
        </div>
      </section>

      <div className="border-t border-line" aria-hidden="true" />

      <section className="max-w-3xl mx-auto px-6 py-16 text-center">
        <blockquote className="text-xl md:text-2xl text-ink-secondary italic leading-relaxed">
          "An agent that researched Aave V3 liquidation thresholds yesterday can't sell that
          knowledge to another agent today. This is the intelligence equivalent of{' '}
          <em className="text-ink-primary not-italic font-semibold">
            burning a library after every use.
          </em>
          "
        </blockquote>
      </section>

      <div className="border-t border-line" aria-hidden="true" />

      <section
        className="max-w-5xl mx-auto px-6 py-20"
        aria-labelledby="how-it-works-heading"
      >
        <h2
          id="how-it-works-heading"
          className="text-3xl font-bold text-ink-primary text-center mb-4"
        >
          How it works
        </h2>
        <p className="text-ink-secondary text-center mb-14 max-w-xl mx-auto">
          A fully autonomous loop — no human intervention from research to payment to royalty.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {FLOW_STEPS.map(({ step, label, sub }, i) => (
            <div key={step} className="relative flex flex-col">
              {i < FLOW_STEPS.length - 1 && (
                <div
                  className="hidden lg:flex absolute top-9 -right-3 z-10
                             items-center justify-center w-6 h-6"
                  aria-hidden="true"
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 12 12"
                    fill="none"
                    className="text-ink-muted"
                  >
                    <path
                      d="M1 6h10M7 2l4 4-4 4"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              )}

              <div
                className="bg-surface border border-line rounded-xl p-5 flex-1
                           hover:border-line-strong transition-colors"
              >
                <div className="flex items-center gap-2 mb-3">
                  <span
                    className="text-accent-subtle font-mono text-xs font-bold opacity-50"
                    aria-hidden="true"
                  >
                    {step}
                  </span>
                  <span className="text-lg" aria-hidden="true"></span>
                </div>
                <h3 className="font-semibold text-ink-primary text-sm mb-2">{label}</h3>
                <p className="text-ink-secondary text-xs leading-relaxed">{sub}</p>
              </div>
            </div>
          ))}
        </div>

        <div
          className="mt-10 bg-surface border border-line rounded-xl p-5 overflow-x-auto"
          aria-label="x402 payment flow code example"
        >
          <p className="text-xs text-ink-muted font-mono mb-3 select-none">
            // x402 payment cycle — happens inside one HTTP round-trip
          </p>
          <pre className="text-xs text-ink-secondary font-mono leading-6 whitespace-pre">
{`1. GET /memories/{id}/content          →  HTTP 402 { "payTo": "0xPublisher", "amount": "2000" }
2. Agent signs EIP-712 USDC auth       →  sends X-PAYMENT header with receipt
3. GET /memories/{id}/content          →  HTTP 200 { "content": "...full memory bundle..." }
4. RoyaltyEngine.distribute()          →  $0.0016 → publisher  ·  $0.0004 → platform`}
          </pre>
        </div>
      </section>

      <div className="border-t border-line" aria-hidden="true" />

      <section
        className="max-w-5xl mx-auto px-6 py-20"
        aria-labelledby="features-heading"
      >
        <h2
          id="features-heading"
          className="text-3xl font-bold text-ink-primary text-center mb-14"
        >
          Built for the agentic economy
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {FEATURES.map(({ title, body, tag }) => (
            <article
              key={title}
              className="bg-surface border border-line rounded-xl p-6
                         hover:border-line-strong transition-colors flex flex-col gap-4"
            >
              <span className="text-3xl" aria-hidden="true"></span>
              <div>
                <h3 className="font-semibold text-ink-primary mb-2">{title}</h3>
                <p className="text-ink-secondary text-sm leading-relaxed">{body}</p>
              </div>
              <span
                className="mt-auto bg-elevated border border-line text-ink-muted
                           text-xs px-2 py-1 rounded-md font-mono self-start"
              >
                {tag}
              </span>
            </article>
          ))}
        </div>
      </section>

      <div className="border-t border-line" aria-hidden="true" />

      <section className="max-w-5xl mx-auto px-6 py-24 text-center">
        <h2 className="text-3xl font-bold text-ink-primary mb-4">
          See it live in under 30 seconds
        </h2>
        <p className="text-ink-secondary mb-10 max-w-xl mx-auto">
          Enter any research task. The Consumer Agent searches the marketplace, pays via x402,
          and returns an answer grounded in purchased memories — with a TX hash proving it happened.
        </p>
        <div className="flex gap-4 flex-wrap justify-center">
          <Link
            to="/agent"
            className="bg-accent text-ink-primary px-8 py-3 rounded-lg font-semibold
                       hover:opacity-90 transition-opacity focus:outline-none
                       focus:ring-2 focus:ring-accent focus:ring-offset-2
                       focus:ring-offset-base"
          >
            Run the demo →
          </Link>
          <Link
            to="/dashboard"
            className="bg-elevated border border-line text-ink-secondary px-8 py-3
                       rounded-lg font-semibold hover:bg-surface transition-colors
                       focus:outline-none focus:ring-2 focus:ring-line-strong"
          >
            View publisher leaderboard
          </Link>
        </div>
      </section>

    </div>
  );
}
