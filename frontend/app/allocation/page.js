"use client";

import { useEffect, useState } from "react";
import { AadhyaSays, InfoDisclosure, TutorialTip } from "../components/Aadhya";
import { ShareButton } from "../components/ShareButton";
import { inr } from "../lib/format";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const ASSET_LABELS = {
  fd_debt: "FDs & Savings",
  gold: "Gold ETF",
  equity: "Equity",
};

export default function Allocation() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [demoMsg, setDemoMsg] = useState(null);

  useEffect(() => {
    fetch(`${API}/me/allocation`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setError("Could not load your allocation right now."));
  }, []);

  const triggerDownturn = async () => {
    const r = await fetch(`${API}/demo/trigger-downturn`, { method: "POST" });
    const d = await r.json();
    setDemoMsg(
      d.equity_amount_before > 0
        ? `Downturn queued: ${inr(d.equity_amount_before)} → ${inr(d.equity_amount_after)}. Open Chat to see Aadhya lead with it.`
        : "No equity allocation yet — buy gold 3+ times first (Chat → \"Buy ₹50 of gold\") to unlock equity, then try this again."
    );
  };

  const resetChat = async () => {
    await fetch(`${API}/demo/reset-chat`, { method: "POST" });
    setDemoMsg("Conversation sequence reset — Chat will start from the FD intro again.");
  };

  if (error) return <Centered>{error}</Centered>;
  if (!data) return <Centered>Loading your allocation...</Centered>;

  return (
    <div className="min-h-screen bg-zinc-50 px-6 py-12 font-sans dark:bg-black">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">
          Here&apos;s how I&apos;d split your {inr(data.total_holdings)}{" "}
          <TutorialTip>
            This split starts 100% FDs/gold — equity only unlocks once you&apos;ve bought gold 3+ times
            (Chat → &quot;Buy ₹50 of gold&quot;, repeat 3x). That&apos;s a deliberate rule: never open a new
            user with market-linked risk.
          </TutorialTip>
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Based on what you already hold — not a generic model portfolio.
        </p>

        <section className="mt-8 space-y-3">
          {data.allocation.map((a) => (
            <div
              key={a.asset_class}
              className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="flex items-baseline justify-between">
                <span className="font-medium text-black dark:text-zinc-50">
                  {ASSET_LABELS[a.asset_class]}
                </span>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">
                  {a.percent}% · {inr(a.amount_inr)}
                </span>
              </div>

              <AadhyaSays>{a.reasoning}</AadhyaSays>

              {a.risk_scenario && (
                <AadhyaSays tone="risk">
                  <p>
                    <span className="font-semibold">If markets fall:</span> this {inr(a.amount_inr)} in
                    equity could drop to{" "}
                    <span className="font-semibold">{inr(a.risk_scenario.worst_case.value_at_trough)}</span>{" "}
                    in a crash like 2020&apos;s ({a.risk_scenario.worst_case.drawdown_percent}%) — and
                    markets like that have recovered within about a year.
                  </p>
                  <p className="mt-2">
                    <span className="font-semibold">If markets rise:</span> invested right after that kind
                    of low, it could grow to roughly{" "}
                    <span className="font-semibold">
                      {inr(a.risk_scenario.best_case.value_after_rebound_approx)}
                    </span>{" "}
                    within about a year.
                  </p>
                  <InfoDisclosure>
                    Worst case: Nifty 50, {a.risk_scenario.worst_case.from_date} to{" "}
                    {a.risk_scenario.worst_case.to_date} (2020 COVID drawdown), recovered to pre-crash
                    level by ~{a.risk_scenario.worst_case.recovered_by_date_approx}. Corroborated by 3
                    independent secondary sources. Best case: Nifty 50 rebound,{" "}
                    {a.risk_scenario.best_case.window} — this figure is approximate, a rounded
                    secondary-source claim rather than an exact index-to-index calculation.
                  </InfoDisclosure>
                </AadhyaSays>
              )}
            </div>
          ))}
        </section>

        <p className="mt-6 text-xs text-zinc-500 dark:text-zinc-400">
          Gold engagement stage: <span className="font-medium">{data.gold_engagement_stage}</span> — this
          allocation adapts as your gold ETF activity grows.
        </p>

        <ShareButton endpoint="/me/share/allocation" label="Share with family" />

        <div className="mt-8 rounded-xl border border-dashed border-zinc-300 p-4 dark:border-zinc-700">
          <p className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            Demo controls (judges only)
            <TutorialTip>
              Suggested judge script: 1) Chat → click &quot;Buy ₹50 of gold&quot; three times to unlock
              equity. 2) Come back here and hit &quot;Simulate downturn&quot;. 3) Open Chat again — Aadhya
              leads with the crash alert unprompted. 4) &quot;Reset conversation sequence&quot; replays the
              whole thing from scratch for the next judge.
            </TutorialTip>
          </p>
          <div className="mt-2 flex gap-2">
            <button
              onClick={triggerDownturn}
              className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs text-black hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-800"
            >
              Simulate 2020-style downturn
            </button>
            <TutorialTip>
              Applies the real 2020 Nifty 50 crash (-39.2%) to your current equity allocation, then queues
              an alert so Aadhya opens the next chat with it. Needs equity &gt; 0 first (see tip above).
            </TutorialTip>
            <button
              onClick={resetChat}
              className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs text-black hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-800"
            >
              Reset conversation sequence
            </button>
            <TutorialTip>
              Wipes this demo user&apos;s chat progress so the next Chat visit starts over from the FD
              intro — useful for re-running the walkthrough for a new judge.
            </TutorialTip>
          </div>
          {demoMsg && <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{demoMsg}</p>}
        </div>
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
