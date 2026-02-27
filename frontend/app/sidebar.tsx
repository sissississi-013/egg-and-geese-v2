"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  Megaphone,
  Plus,
  Activity,
  BarChart3,
  Brain,
  Moon,
  Sun,
} from "lucide-react";
import { useTheme } from "./theme-provider";

export default function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  const links = [
    { href: "/", label: "Dashboard", icon: Home },
    { href: "/campaigns", label: "Campaigns", icon: Megaphone },
    { href: "/campaigns/new", label: "New Campaign", icon: Plus },
    { href: "/activity", label: "Activity Feed", icon: Activity },
    { href: "/analytics", label: "Analytics", icon: BarChart3 },
    { href: "/knowledge", label: "Knowledge Graph", icon: Brain },
  ];

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col border-r border-border bg-surface-raised">
      <div className="flex h-16 items-center gap-3 border-b border-border px-6">
        <Image
          src="/logo.png"
          alt="Egg & Geese"
          width={32}
          height={32}
          className="h-8 w-8 rounded-lg object-contain"
        />
        <div>
          <h1 className="text-sm font-bold tracking-tight text-foreground">
            Egg & Geese
          </h1>
          <p className="text-[10px] font-medium uppercase tracking-widest text-brand-500">
            vibe marketing v2
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-500/10 text-brand-500"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {link.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-brand-500 animate-pulse" />
          <span className="text-xs text-muted-foreground">Swarm Active</span>
        </div>
        <button
          onClick={toggleTheme}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
          {theme === "dark" ? "Light Mode" : "Dark Mode"}
        </button>
      </div>
    </aside>
  );
}
