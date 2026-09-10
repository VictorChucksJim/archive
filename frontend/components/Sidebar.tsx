"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { storage as storageApi } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { useAuth } from "@/hooks/useAuth";
import type { StorageUsage } from "@/types";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const router = useRouter();
  const [usage, setUsage] = useState<StorageUsage | null>(null);

  useEffect(() => {
    storageApi.usage().then(setUsage).catch(() => setUsage(null));
  }, [pathname]);

  const pct = usage ? Math.min(100, Math.round((usage.used_bytes / usage.quota_bytes) * 100)) : 0;

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const linkClass = (active: boolean) =>
    `block rounded-lg px-3 py-2 text-sm font-medium ${
      active ? "bg-blue-50 text-accent" : "text-slate-600 hover:bg-slate-100"
    }`;

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-slate-200 bg-white p-4">
      <div className="mb-6 px-2">
        <h1 className="text-lg font-bold text-ink">ARCHIVE</h1>
        {user && <p className="truncate text-xs text-slate-400">{user.email}</p>}
      </div>

      <nav className="flex-1 space-y-1">
        <Link href="/dashboard" className={linkClass(pathname === "/dashboard")}>
          My Archive
        </Link>
        <Link href="/trash" className={linkClass(pathname === "/trash")}>
          Trash
        </Link>
      </nav>

      <div className="mt-4 space-y-2 border-t border-slate-200 pt-4">
        {usage && (
          <div className="px-2">
            <div className="mb-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
            </div>
            <p className="text-xs text-slate-400">
              {formatBytes(usage.used_bytes)} of {formatBytes(usage.quota_bytes)} used
            </p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-500 hover:bg-slate-100"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
