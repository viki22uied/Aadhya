"use client";

import { useEffect, useRef, useState } from "react";
import { inr } from "../lib/format";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Interactive draw-amount control — replaces the old fixed-amount button.
// Recomputes the offer live via GET /me/fd/{id}/loan-offer (the same
// deterministic rule function the draw endpoint uses) as the user drags,
// debounced so it doesn't fire on every pixel of movement.
export function LoanDrawSlider({ fd, onDraw, drawing, result }) {
  const [amount, setAmount] = useState(Math.round(fd.loan_offer.max_loan_amount * 0.5));
  const [offer, setOffer] = useState(fd.loan_offer);
  const debounceRef = useRef(null);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetch(`${API}/me/fd/${fd.id}/loan-offer`)
        .then((r) => r.json())
        .then(setOffer)
        .catch(() => {});
    }, 200);
    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [amount]);

  return (
    <div>
      <input
        type="range"
        min={0}
        max={Math.round(fd.loan_offer.max_loan_amount)}
        step={1000}
        value={amount}
        onChange={(e) => setAmount(Number(e.target.value))}
        className="mt-2 w-full accent-emerald-600"
      />
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-semibold text-black dark:text-zinc-50">{inr(amount)}</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          est. {offer.interest_rate_min_percent}%–{offer.interest_rate_max_percent}%
        </span>
      </div>

      <button
        disabled={drawing || amount <= 0}
        onClick={() => onDraw(fd.id, amount)}
        className="mt-2 rounded-full border border-emerald-300 px-4 py-1.5 text-xs font-medium text-emerald-900 hover:bg-emerald-100 disabled:opacity-50 dark:border-emerald-700 dark:text-emerald-200 dark:hover:bg-emerald-900/40"
      >
        Draw {inr(amount)} now
      </button>

      {result && (
        <p className="mt-2 text-xs">
          {result.error
            ? result.error
            : `Done — I've moved ${inr(result.amount_drawn)} to your account at ${result.interest_rate_min_percent}%–${result.interest_rate_max_percent}%.`}
        </p>
      )}
    </div>
  );
}
