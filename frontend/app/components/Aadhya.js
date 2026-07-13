"use client";

// Persistent Aadhya persona components — PRD Section 3 principle 8: the
// avatar's presence is load-bearing, not cosmetic, so it lives in every
// screen via the root layout, not bolted onto one page.
import Link from "next/link";
import { useLanguage } from "./LanguageContext";

export function AadhyaAvatar({ size = 40 }) {
  return (
    <div
      style={{ width: size, height: size }}
      className="flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 font-semibold text-white"
    >
      <span style={{ fontSize: size * 0.45 }}>A</span>
    </div>
  );
}

export function AadhyaHeader() {
  const { lang, setLang } = useLanguage();

  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-zinc-200 bg-white/90 px-6 py-3 backdrop-blur dark:border-zinc-800 dark:bg-black/90">
      <AadhyaAvatar size={36} />
      <div>
        <p className="text-sm font-semibold text-black dark:text-zinc-50">Aadhya</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">your wealth advisor</p>
      </div>
      <nav className="ml-auto flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
        <Link href="/" className="hover:text-black dark:hover:text-zinc-50">
          Chat
        </Link>
        <Link href="/onboarding" className="hover:text-black dark:hover:text-zinc-50">
          Your accounts
        </Link>
        <Link href="/allocation" className="hover:text-black dark:hover:text-zinc-50">
          Allocation
        </Link>
        <div className="flex overflow-hidden rounded-full border border-zinc-300 dark:border-zinc-700">
          <button
            onClick={() => setLang("en")}
            className={`px-2 py-1 ${lang === "en" ? "bg-violet-600 text-white" : "text-zinc-500 dark:text-zinc-400"}`}
          >
            EN
          </button>
          <button
            onClick={() => setLang("hi")}
            title="Hindi — chat replies translated via Google Translate. Other screens still English-only."
            className={`px-2 py-1 ${lang === "hi" ? "bg-violet-600 text-white" : "text-zinc-500 dark:text-zinc-400"}`}
          >
            हिं
          </button>
        </div>
      </nav>
    </header>
  );
}

// Speech-bubble treatment for Aadhya's own explanatory voice — visually
// distinct from the raw data cards around it, per the user's request to
// separate "Aadhya talking" from "numbers reported."
export function AadhyaSays({ children, tone = "neutral" }) {
  const toneClasses = {
    neutral: "bg-violet-50 dark:bg-violet-950/30",
    caution: "bg-amber-50 dark:bg-amber-950/30",
    opportunity: "bg-emerald-50 dark:bg-emerald-950/30",
    risk: "bg-rose-50 dark:bg-rose-950/30",
  };
  return (
    <div className={`mt-3 flex gap-2 rounded-xl p-3 text-sm ${toneClasses[tone]}`}>
      <AadhyaAvatar size={22} />
      <div className="flex-1 text-zinc-800 dark:text-zinc-200">{children}</div>
    </div>
  );
}

// Native <details>/<summary> — no JS state needed for a simple expandable.
// Keeps sourcing/citation language out of default-visible copy (PRD
// principle 9: zero prior financial vocabulary) while still keeping it
// auditable for judges/power users who tap in.
export function InfoDisclosure({ summary, children }) {
  return (
    <details className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
      <summary className="cursor-pointer select-none hover:text-zinc-700 dark:hover:text-zinc-300">
        ℹ how we calculate this
      </summary>
      <div className="mt-1 pl-4">{children}</div>
    </details>
  );
}

// Judges land on this app cold with no walkthrough — a small "?" badge next
// to any non-obvious action that pops its explanation open right there,
// instead of a separate onboarding doc nobody reads before clicking around.
export function TutorialTip({ children }) {
  return (
    <details className="group relative inline-block align-middle">
      <summary className="inline-flex h-5 w-5 cursor-pointer select-none list-none items-center justify-center rounded-full border border-violet-400 text-[11px] font-semibold text-violet-600 hover:bg-violet-50 dark:border-violet-600 dark:text-violet-300 dark:hover:bg-violet-950/40">
        ?
      </summary>
      <div className="absolute z-20 mt-2 w-64 rounded-lg border border-violet-300 bg-white p-3 text-xs leading-relaxed text-zinc-700 shadow-lg dark:border-violet-700 dark:bg-zinc-900 dark:text-zinc-300">
        {children}
      </div>
    </details>
  );
}
