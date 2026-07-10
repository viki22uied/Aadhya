"use client";

import { useEffect, useState } from "react";
import { AadhyaSays, InfoDisclosure } from "../components/Aadhya";
import { LoanDrawSlider } from "../components/LoanDrawSlider";
import { ShareButton } from "../components/ShareButton";
import { inr } from "../lib/format";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Onboarding() {
  const [snapshot, setSnapshot] = useState(null);
  const [gold, setGold] = useState(null);
  const [milestones, setMilestones] = useState(null);
  const [goals, setGoals] = useState(null);
  const [newGoalName, setNewGoalName] = useState("");
  const [error, setError] = useState(null);
  const [buying, setBuying] = useState(false);
  const [drawingFdId, setDrawingFdId] = useState(null);
  const [loanResults, setLoanResults] = useState({});

  const loadMilestones = () => {
    fetch(`${API}/me/gold-milestones`)
      .then((r) => r.json())
      .then(setMilestones)
      .catch(() => {});
  };

  const loadGoals = () => {
    fetch(`${API}/me/goals`)
      .then((r) => r.json())
      .then(setGoals)
      .catch(() => {});
  };

  useEffect(() => {
    fetch(`${API}/me/fd-snapshot`)
      .then((r) => r.json())
      .then(setSnapshot)
      .catch(() => setError("Could not load your snapshot right now."));
    fetch(`${API}/me/gold-snapshot`)
      .then((r) => r.json())
      .then(setGold)
      .catch(() => {});
    loadMilestones();
    loadGoals();
  }, []);

  const createGoal = async () => {
    if (!newGoalName.trim()) return;
    await fetch(`${API}/me/goals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newGoalName }),
    });
    setNewGoalName("");
    loadGoals();
  };

  const assignFdGoal = async (fdId, goalId) => {
    if (!goalId) return;
    await fetch(`${API}/me/fd/${fdId}/assign-goal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal_id: Number(goalId) }),
    });
    const r = await fetch(`${API}/me/fd-snapshot`);
    setSnapshot(await r.json());
    loadGoals();
  };

  const assignGoldGoal = async (goalId) => {
    if (!goalId) return;
    await fetch(`${API}/me/gold/assign-goal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal_id: Number(goalId) }),
    });
    loadGoals();
  };

  const buyGold = async (amount) => {
    setBuying(true);
    try {
      const r = await fetch(`${API}/me/gold-snapshot/purchase`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount_inr: amount }),
      });
      setGold(await r.json());
      loadMilestones();
    } finally {
      setBuying(false);
    }
  };

  const drawLoan = async (fdId, amount) => {
    setDrawingFdId(fdId);
    try {
      const r = await fetch(`${API}/me/fd/${fdId}/loan-draw`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount_inr: amount }),
      });
      const data = await r.json();
      setLoanResults((prev) => ({ ...prev, [fdId]: r.ok ? data : { error: data.detail } }));
    } finally {
      setDrawingFdId(null);
    }
  };

  if (error) return <Centered>{error}</Centered>;
  if (!snapshot) return <Centered>Loading your snapshot...</Centered>;

  const totalHoldings = snapshot.savings_balance + snapshot.total_fd_current_value;

  return (
    <div className="min-h-screen bg-zinc-50 px-6 py-12 font-sans dark:bg-black">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">
          I looked at your accounts — here&apos;s what&apos;s actually happening with your money.
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          You&apos;ve got {inr(totalHoldings)}{" "}working for you today. No judgment, just what&apos;s real.
        </p>

        <section className="mt-8 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Savings account</h2>
          <p className="mt-1 text-xl font-semibold text-black dark:text-zinc-50">
            {inr(snapshot.savings_balance)}
          </p>
        </section>

        <section className="mt-4 space-y-3">
          <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            Fixed deposits ({snapshot.fixed_deposits.length})
          </h2>
          {snapshot.fixed_deposits.map((fd) => (
            <div
              key={fd.id}
              className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="flex items-baseline justify-between">
                <span className="text-black dark:text-zinc-50">{inr(fd.principal)} at {fd.interest_rate_percent}%</span>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  matures {fd.maturity_date}
                </span>
              </div>

              <div className="mt-2 flex items-center gap-2">
                {fd.goal_name ? (
                  <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-800 dark:bg-violet-900/40 dark:text-violet-300">
                    🎯 {fd.goal_name}
                  </span>
                ) : (
                  goals &&
                  goals.length > 0 && (
                    <select
                      onChange={(e) => assignFdGoal(fd.id, e.target.value)}
                      defaultValue=""
                      className="rounded-full border border-zinc-300 bg-white px-2 py-0.5 text-xs text-black dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                    >
                      <option value="" disabled>
                        Tag to a goal...
                      </option>
                      {goals.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.name}
                        </option>
                      ))}
                    </select>
                  )
                )}
              </div>
              <div className="mt-2 flex gap-6 text-sm">
                <span className="text-zinc-600 dark:text-zinc-400">
                  Worth today: <span className="font-medium text-black dark:text-zinc-50">{inr(fd.current_value)}</span>
                </span>
                <span className="text-zinc-600 dark:text-zinc-400">
                  At maturity: <span className="font-medium text-black dark:text-zinc-50">{inr(fd.maturity_value)}</span>
                </span>
              </div>

              <AadhyaSays tone="caution">
                <p>
                  I checked what tax and inflation actually do to this one — after {snapshot.tax_slab_percent}%
                  tax, it&apos;s really worth{" "}
                  <span className="font-semibold">{inr(fd.post_tax_reality.inflation_adjusted_value)}</span>{" "}
                  in today&apos;s money. That&apos;s a real gain of{" "}
                  <span className="font-semibold">{inr(fd.post_tax_reality.real_gain)}</span>{" "}
                  ({fd.post_tax_reality.real_annual_yield_percent}%/yr).
                </p>
                <InfoDisclosure>
                  Tax at your {snapshot.tax_slab_percent}% slab (not the 10% TDS rate — that's just
                  withholding, your real liability is your slab rate). Inflation assumption: All-India
                  CPI YoY, {fd.post_tax_reality.cpi_yoy_assumption_percent}%, MoSPI press release, May
                  2026 (released 2026-06-12).
                </InfoDisclosure>
              </AadhyaSays>

              <AadhyaSays tone="opportunity">
                <p>
                  Need cash before this matures? I can get you up to{" "}
                  <span className="font-semibold">{inr(fd.loan_offer.max_loan_amount)}</span> against
                  it right now, at an estimated {fd.loan_offer.interest_rate_min_percent}%–
                  {fd.loan_offer.interest_rate_max_percent}%. It keeps earning interest the whole time —
                  you only pay for what you actually draw.
                </p>
                <InfoDisclosure>
                  Max amount uses a {fd.loan_offer.ltv_percent}% loan-to-value, sourced from
                  Policybazaar/BankBazaar aggregator data on IDBI's overdraft-against-FD product (not
                  independently confirmed on idbi.bank.in). Rate range is FD rate + 1–2%, a general
                  market range (RBI FAQ, Paisabazaar, BankBazaar) — not an IDBI-specific figure, pending
                  IDBI's confirmed rate card.
                </InfoDisclosure>

                <LoanDrawSlider
                  fd={fd}
                  onDraw={drawLoan}
                  drawing={drawingFdId === fd.id}
                  result={loanResults[fd.id]}
                />
                <ShareButton endpoint={`/me/share/loan-offer/${fd.id}`} label="Share with family" />
              </AadhyaSays>
            </div>
          ))}
        </section>

        <AadhyaSays>
          Across everything: your {inr(snapshot.total_fd_principal)} in FDs will become{" "}
          {inr(snapshot.total_fd_maturity_value)} at maturity.
        </AadhyaSays>

        <section className="mt-8 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Your goals</h2>

          {goals && goals.length > 0 && (
            <div className="mt-3 space-y-2">
              {goals.map((g) => (
                <div key={g.id} className="flex items-baseline justify-between text-sm">
                  <span className="text-black dark:text-zinc-50">🎯 {g.name}</span>
                  <span className="text-zinc-500 dark:text-zinc-400">{inr(g.total_value)}</span>
                </div>
              ))}
            </div>
          )}

          <div className="mt-3 flex gap-2">
            <input
              value={newGoalName}
              onChange={(e) => setNewGoalName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createGoal()}
              placeholder="e.g. Emergency cushion"
              className="flex-1 rounded-full border border-zinc-300 bg-white px-3 py-1.5 text-sm text-black outline-none focus:border-violet-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
            <button
              onClick={createGoal}
              className="rounded-full bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700"
            >
              Add goal
            </button>
          </div>
        </section>

        <div className="mt-8 rounded-xl border border-dashed border-zinc-300 p-4 dark:border-zinc-700">
          <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Demo controls (judges only)</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {snapshot.fixed_deposits.map((fd) => (
              <button
                key={fd.id}
                onClick={async () => {
                  await fetch(`${API}/demo/mature-fd/${fd.id}`, { method: "POST" });
                  location.reload();
                }}
                className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs text-black hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-800"
              >
                Mature FD #{fd.id} now
              </button>
            ))}
            {[10000, 50000].map((amt) => (
              <button
                key={amt}
                onClick={async () => {
                  await fetch(`${API}/demo/add-savings`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ amount_inr: amt }),
                  });
                  location.reload();
                }}
                className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs text-black hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-800"
              >
                + {inr(amt)} to savings
              </button>
            ))}
          </div>
        </div>

        {gold && (
          <section className="mt-8 rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Gold ETF</h2>
              {goals && goals.length > 0 && (
                <select
                  onChange={(e) => assignGoldGoal(e.target.value)}
                  defaultValue=""
                  className="rounded-full border border-zinc-300 bg-white px-2 py-0.5 text-xs text-black dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                >
                  <option value="" disabled>
                    Tag to a goal...
                  </option>
                  {goals.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <p className="mt-3 text-xl font-semibold text-black dark:text-zinc-50">
              {inr(gold.current_value)}{" "}
              <span className="text-sm font-normal text-zinc-500 dark:text-zinc-400">
                ({gold.total_units_grams}g)
              </span>
            </p>

            <AadhyaSays>
              <p>
                Want to start small in gold? I use SEBI-regulated Gold ETFs here, not &quot;digital
                gold&quot; — it&apos;s the safer, regulated way in.
              </p>
              <InfoDisclosure>
                SEBI publicly cautioned (8 Nov 2025) that digital gold/e-gold products aren't regulated
                by SEBI or RBI and have no formal grievance redressal — so this uses SEBI-regulated Gold
                ETFs instead. Price shown ({inr(gold.current_price_per_gram_inr)}/gram) is demo data, not
                a live market feed; distribution partner pending IDBI's brokerage tie-up.
              </InfoDisclosure>

              <div className="mt-3 flex gap-2">
                {[10, 50, 100].map((amt) => (
                  <button
                    key={amt}
                    disabled={buying}
                    onClick={() => buyGold(amt)}
                    className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium text-black hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-800"
                  >
                    + {inr(amt)}
                  </button>
                ))}
              </div>
            </AadhyaSays>

            <ShareButton endpoint="/me/share/gold" label="Share with family" />

            {milestones && (
              <div className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-950/40">
                <div className="flex items-baseline justify-between">
                  <span className="font-medium text-black dark:text-zinc-50">
                    {milestones.current_streak_days > 0
                      ? `${milestones.current_streak_days}-day streak`
                      : "No active streak"}
                  </span>
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    Best: {milestones.longest_streak_days} day{milestones.longest_streak_days === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {milestones.milestones.map((m) => (
                    <span
                      key={m.amount_inr}
                      className={`rounded-full px-2 py-1 text-xs ${
                        m.reached
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                          : "bg-zinc-200 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500"
                      }`}
                    >
                      {inr(m.amount_inr)} {m.reached ? "✓" : ""}
                    </span>
                  ))}
                </div>
                <InfoDisclosure>{milestones.how_this_works}</InfoDisclosure>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function Centered({ children }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
      <p className="text-zinc-600 dark:text-zinc-400">{children}</p>
    </div>
  );
}
