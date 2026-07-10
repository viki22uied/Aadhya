"use client";

import { createContext, useContext, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState("en");
  const [hindiError, setHindiError] = useState(null);

  // Real translation via Google Translate's free endpoint (see
  // backend/translate_hindi.py). Returns the original English texts
  // unchanged if Hindi isn't reachable, and sets hindiError so the UI can say
  // so honestly instead of silently staying in English.
  const translate = async (texts) => {
    if (lang !== "hi" || texts.length === 0) return texts;
    try {
      const r = await fetch(`${API}/translate/hindi`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texts }),
      });
      const data = await r.json();
      if (data.error) {
        setHindiError(data.error);
        return texts;
      }
      setHindiError(null);
      return data.translated;
    } catch {
      setHindiError("unreachable");
      return texts;
    }
  };

  return (
    <LanguageContext.Provider value={{ lang, setLang, translate, hindiError }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
