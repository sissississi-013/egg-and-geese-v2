import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "./theme-provider";
import Sidebar from "./sidebar";

export const metadata: Metadata = {
  title: "Egg & Geese v2 — Self-Evolving Vibe Marketing",
  description:
    "Multi-agent platform that autonomously scouts, engages, and learns across social media.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-surface font-sans antialiased">
        <ThemeProvider>
          <Sidebar />
          <main className="ml-64 min-h-screen p-8">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
