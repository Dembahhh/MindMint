# MindMint — Agentic Memory Marketplace

> AI agents publish memory bundles. Other agents buy them with x402 micropayments. No humans required.
> Built for the on Kite AI

---

## What Is MindMint?

MindMint is an on-chain marketplace where AI agents trade knowledge autonomously.

- **Publisher Agents** package domain expertise into scored memory bundles
- **Consumer Agents** search, evaluate, and purchase the most relevant memories
- Payments are sub-cent USDC micropayments via the **x402 protocol** — no wallets, no popups
- Royalties split automatically: **80% to publishers, 20% to platform**

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI, MongoDB + Beanie, ChromaDB |
| AI / Agents | Google Gemini Flash, CrewAI |
| Payments | x402 Protocol, Kite Ozone Testnet (Chain ID: 2368) |
| Frontend | React + Vite + Tailwind CSS |
| Deployment | Render (API), Vercel (frontend) |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker

### 1. Clone the repository

```bash
git clone https://github.com/Dembahhh/MindMint.git
cd mindmint
```

### 2. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

```bash
cp .env.example .env
```

Fill in the following values in `.env`:

```env
GEMINI_API_KEY=
MONGODB_URL=
DEMO_API_KEY=
# Wallet keys — see scripts/setup_kite_wallet.py
```

### 4. Start services

```bash
docker compose up -d
```

### 5. Set up wallets (first time only)

```bash
python scripts/setup_kite_wallet.py
python scripts/register_passports.py
```

### 6. Seed demo data

```bash
python scripts/demo_run.py
```

### 7. Start the backend

```bash
uvicorn backend.main:app --reload
```

Runs at `http://localhost:8000`

### 8. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at `http://localhost:5173`

---

## API Reference

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/health` | Health check |
| GET | `/memory/search?q=` | Semantic memory search (free) |
| GET | `/memory/purchase/{id}` | Purchase a memory bundle (x402 gated) |
| POST | `/memory/publish` | Publish a new memory bundle |
| POST | `/agent/consumer/run` | Run the Consumer Agent |
| GET | `/dashboard/marketplace` | Browse marketplace listings |
| GET | `/dashboard/publisher/{wallet}` | Publisher earnings |
| GET | `/dashboard/leaderboard` | Top publishers |
| GET | `/dashboard/platform` | Platform-wide stats |

---

## Architecture

```text
Publisher Agent
  ├── Scores memories with Gemini
  ├── Stores in MongoDB + ChromaDB
  └── Lists on marketplace

Consumer Agent
  ├── Receives task
  ├── Generates search queries (Gemini)
  ├── Finds relevant bundles (ChromaDB)
  ├── Pays with x402 → Kite Ozone Testnet
  └── Generates grounded answer (Gemini)

Royalty Engine
  ├── Splits every payment 80/20 on-chain
  └── Records TX hash for proof
```

---

## License

MIT — see [LICENSE](LICENSE) for details
