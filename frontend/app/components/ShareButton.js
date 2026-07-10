"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// C4: Joint/Family View. Doesn't integrate the real WhatsApp API — that's
// explicitly out of scope for the demo — instead uses the Web Share API
// (opens the native share sheet, WhatsApp included, on mobile/supported
// desktop browsers) with a copy-to-clipboard fallback, plus a downloadable
// PNG summary card for when neither is convenient.
function wrapText(ctx, text, maxWidth) {
  const lines = [];
  for (const paragraph of text.split("\n")) {
    if (paragraph === "") {
      lines.push("");
      continue;
    }
    const words = paragraph.split(" ");
    let line = "";
    for (const word of words) {
      const test = line ? `${line} ${word}` : word;
      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);
        line = word;
      } else {
        line = test;
      }
    }
    lines.push(line);
  }
  return lines;
}

function downloadImage(text) {
  const canvas = document.createElement("canvas");
  const width = 640;
  const padding = 32;
  const ctx = canvas.getContext("2d");
  ctx.font = "16px sans-serif";
  const lines = wrapText(ctx, text, width - padding * 2);
  const lineHeight = 26;
  const height = padding * 2 + 40 + lines.length * lineHeight;

  canvas.width = width;
  canvas.height = height;

  ctx.fillStyle = "#0a0a0a";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#a855f7";
  ctx.beginPath();
  ctx.arc(padding + 14, padding + 14, 14, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 16px sans-serif";
  ctx.fillText("Aadhya", padding + 38, padding + 19);

  ctx.font = "16px sans-serif";
  ctx.fillStyle = "#e4e4e7";
  lines.forEach((line, i) => {
    ctx.fillText(line, padding, padding + 50 + i * lineHeight);
  });

  canvas.toBlob((blob) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "aadhya-summary.png";
    a.click();
    URL.revokeObjectURL(url);
  });
}

export function ShareButton({ endpoint, label = "Share" }) {
  const [status, setStatus] = useState(null);

  const share = async () => {
    const r = await fetch(`${API}${endpoint}`);
    const { text } = await r.json();

    if (navigator.share) {
      try {
        await navigator.share({ text });
        return;
      } catch {
        // user cancelled the share sheet — fall through to clipboard copy
      }
    }
    await navigator.clipboard.writeText(text);
    setStatus("Copied — paste it into WhatsApp or wherever.");
    setTimeout(() => setStatus(null), 3000);

    downloadImage(text);
  };

  return (
    <div className="mt-2">
      <button
        onClick={share}
        className="rounded-full border border-zinc-300 px-3 py-1.5 text-xs font-medium text-black hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-800"
      >
        {label}
      </button>
      {status && <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{status}</p>}
    </div>
  );
}
