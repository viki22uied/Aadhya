"use client";

import { useState } from "react";
import { inr } from "../lib/format";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Renders a structured card for a tool call's result, inline in chat — the
// same data the /onboarding and /allocation pages show, but reached through
// the conversation instead of a separate tab (per the requirement that
// structured views be things Aadhya can surface mid-chat, not disconnected).
export function ToolResultCard({ name, result }) {
  if (result?.error) {
    return (
      <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300">
        {result.error}
      </div>
    );
  }

  if (name === "get_fd_snapshot") {
    return (
      <div className="mt-2 space-y-2">
        {result.fixed_deposits.map((fd) => (
          <div
            key={fd.id}
            className="rounded-lg border border-zinc-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="flex items-baseline justify-between">
              <span className="text-black dark:text-zinc-50">
                FD #{fd.id}: {inr(fd.principal)} at {fd.interest_rate_percent}%
              </span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">matures {fd.maturity_date}</span>
            </div>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Worth today: {inr(fd.current_value)} · At maturity: {inr(fd.maturity_value)}
            </p>
          </div>
        ))}
      </div>
    );
  }

  if (name === "get_loan_offer") {
    return (
      <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm dark:border-emerald-900 dark:bg-emerald-950/30">
        Max: <span className="font-semibold">{inr(result.max_loan_amount)}</span> at{" "}
        {result.interest_rate_min_percent}%–{result.interest_rate_max_percent}%
      </div>
    );
  }

  if (name === "get_allocation") {
    return (
      <div className="mt-2 space-y-2">
        {result.allocation.map((a) => (
          <div
            key={a.asset_class}
            className="rounded-lg border border-zinc-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="flex items-baseline justify-between">
              <span className="font-medium text-black dark:text-zinc-50">{a.asset_class}</span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                {a.percent}% · {inr(a.amount_inr)}
              </span>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (name === "get_risk_scenario") {
    if ("equity_amount_before" in result) {
      // C3 downturn event shape, not the C2 what-if shape.
      return (
        <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm dark:border-rose-900 dark:bg-rose-950/30">
          {inr(result.equity_amount_before)} → {inr(result.equity_amount_after)} (
          {result.drawdown_percent.toFixed(1)}%)
        </div>
      );
    }
    return (
      <div className="mt-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm dark:border-rose-900 dark:bg-rose-950/30">
        Worst case: {inr(result.worst_case.value_at_trough)} · Best case:{" "}
        {inr(result.best_case.value_after_rebound_approx)}
      </div>
    );
  }

  if (name === "get_gold_snapshot") {
    return (
      <div className="mt-2 rounded-lg border border-zinc-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900">
        {inr(result.current_value)} ({result.total_units_grams}g)
      </div>
    );
  }

  if (name === "get_ladder_proposal") {
    return <LadderProposalCard proposal={result} />;
  }

  return null;
}

// B2: one-tap approval for the re-ladder/sweep split — the concrete
// interactive action inline in chat, not just a read-only summary.
function LadderProposalCard({ proposal }) {
  const [done, setDone] = useState(null);
  const [approving, setApproving] = useState(false);

  const approve = async () => {
    setApproving(true);
    try {
      const r = await fetch(`${API}/me/fd/${proposal.fixed_deposit_id}/approve-ladder`, { method: "POST" });
      setDone(await r.json());
    } finally {
      setApproving(false);
    }
  };

  if (done) {
    return (
      <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm dark:border-emerald-900 dark:bg-emerald-950/30">
        Done — new FD opened at {inr(done.ladder_amount)}, {inr(done.sweep_amount)} moved to the steadier option.
      </div>
    );
  }

  return (
    <div className="mt-2 rounded-lg border border-zinc-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-black dark:text-zinc-50">
        New FD: {inr(proposal.ladder_amount)} at {proposal.ladder_rate_percent}%
      </p>
      <p className="mt-1 text-black dark:text-zinc-50">
        Steadier option: {inr(proposal.sweep_amount)} at {proposal.sweep_yield_percent}%
      </p>
      <button
        onClick={approve}
        disabled={approving}
        className="mt-2 rounded-full border border-emerald-300 px-4 py-1.5 text-xs font-medium text-emerald-900 hover:bg-emerald-100 disabled:opacity-50 dark:border-emerald-700 dark:text-emerald-200 dark:hover:bg-emerald-900/40"
      >
        Go ahead
      </button>
    </div>
  );
}
