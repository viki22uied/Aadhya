import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AadhyaHeader } from "./components/Aadhya";
import { LanguageProvider } from "./components/LanguageContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "Aadhya — your wealth advisor",
  description: "AI-driven wealth advisory: FDs, gold ETF micro-SIP, loans against FD, and portfolio allocation.",
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <LanguageProvider>
          <AadhyaHeader />
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
