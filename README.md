# Aadhya — Digital Wealth Advisory

Aadhya is a conversational digital wealth advisor built for IDBI Bank's mobile app. It exists to solve a specific, narrower problem than "recommend better investments": Indian retail customers aren't failing to invest because they lack information — they avoid market-linked products for structural and psychological reasons (inertia, low financial literacy, inherited risk-aversion, and past product failures that ignored a customer's whole financial picture).

Aadhya is built around a **trust-building sequence**, not a generic recommendation engine:

1. Show the customer what they already have (FDs, savings) — no market pitch, no jargon.
2. Reveal what tax and inflation are actually doing to those deposits.
3. Offer a small, regulated gold ETF habit as the first market-adjacent step.
4. Only then introduce equity/allocation — and even that adapts to how much trust has actually been built.
5. Never go silent during a market downturn, and never let a matured FD sit unmanaged.

Every number Aadhya shows comes from a plain, auditable Python function — never from an LLM guessing. The LLM's only job is to hold a conversation and decide which function to call; it never computes a rupee amount, percentage, or rate itself.

## Features

| Area | What it does |
|---|---|
| **FD & Savings Snapshot** | Shows real savings/FD balances, current and at-maturity value |
| **Post-Tax Reality Panel** | Post-tax, inflation-adjusted real yield per FD (cites MoSPI CPI data) |
| **Gold ETF Micro-SIP** | ₹10–100 recurring gold ETF investing — SEBI-regulated, explicitly not "digital gold" (per SEBI's Nov 2025 caution) |
| **Loan Against FD** | Interactive, one-tap borrowing against an FD without breaking it — live slider recomputes the offer as you drag |
| **Rule-Based Allocation** | Deterministic FD/gold/equity split, with one-sentence reasoning per asset class |
| **Rupee-Framed Risk Explainer** | Shows real 2020-crash worst-case and rebound best-case scenarios for equity exposure, in rupees |
| **Downturn Presence Protocol** | Proactively messages the user during a simulated market downturn — never waits to be asked |
| **FD Ladder Autopilot** | On FD maturity, proposes a re-ladder + debt-sweep split, one-tap approval |
| **Joint/Family View** | Shareable summary cards (WhatsApp-friendly) for a spouse/parent to review |
| **Transparent Milestones** | Honest gold-savings streaks and milestones, with an explicit "how this works" disclosure — no dark patterns |
| **Goal-Based Framing** | Tag FDs/gold to named goals ("Emergency cushion") — Aadhya references holdings by goal, not just instrument |
| **Conversational Chat** | Real tool-calling LLM chat (Groq), with a hard 2-sentence-per-message brevity rule and zero jargon |
| **Hindi Support** | Toggleable Hindi translation for chat (Google Translate), defaults to English |

## Tech stack

- **Frontend:** Next.js (App Router) + Tailwind CSS
- **Backend:** FastAPI (Python)
- **Database:** SQLite
- **LLM:** Groq (OpenAI-compatible API), tool-calling
- **Translation:** Google Translate (free endpoint)
- **Voice input:** Browser Web Speech API (English only)

## Running locally

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt
cp .env.example .env   # then add your own Groq API key
./venv/Scripts/python -m uvicorn main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Visit `http://localhost:3000` — the chat screen is the landing page, with links to the FD/savings snapshot (`/onboarding`) and the allocation breakdown (`/allocation`).

### Demo controls

Both `/onboarding` and `/allocation` include a "Demo controls" panel for judges to simulate scenarios on demand:
- Mature an FD (triggers the ladder-autopilot proposal)
- Simulate a 2020-style market downturn
- Top up the savings balance
- Reset the conversation sequence

## Deploying on Render

A `render.yaml` blueprint at the repo root defines both services:

1. In the Render dashboard: **New → Blueprint**, point it at this repo.
2. Render will create two web services — `aadhya-backend` (FastAPI) and `aadhya-frontend` (Next.js).
3. On the backend service, set `LLM_API_KEY` (your Groq key) — it's marked `sync: false` in the blueprint so Render won't ask for it in the repo, only in the dashboard.
4. Once both services have deployed, check their actual assigned URLs (they may differ from the `*.onrender.com` defaults in `render.yaml` if those names were taken):
   - Update `CORS_ORIGINS` on the **backend** service to the frontend's real URL.
   - Update `NEXT_PUBLIC_API_URL` on the **frontend** service to the backend's real URL, then trigger a redeploy of the frontend (this variable is baked in at build time, so a redeploy is required after changing it).

Note: SQLite lives on local disk and resets on every new deploy (Render's free-tier disk isn't persistent across deploys) — fine for a demo, not for production data.

## Data sourcing

Every figure that represents a real-world fact (CPI, G-Sec yield, loan-to-value, historical drawdowns) is cited in code comments at its source, with an explicit note on whether it's a confirmed primary-source figure or a best-available secondary estimate. Where the PRD required a data point that wasn't available anywhere, the gap is flagged in code rather than filled with an invented number — for example, IDBI's actual loan-against-FD interest spread isn't publicly available, so that figure is clearly labeled illustrative and pending IDBI's own rate card.
