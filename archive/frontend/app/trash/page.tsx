"use client";

import { useCallback, useEffect, useState } from "react";
import { trash as trashApi, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { Button, ErrorBanner } from "@/components/ui";
import type { TrashItem } from "@/types";

export default function TrashPage() {
  const [items, setItems] = useState<TrashItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await trashApi.list());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load Trash.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function restore(item: TrashItem) {
    await trashApi.restore(item.id);
    await load();
  }

  async function permanentlyDelete(item: TrashItem) {
    if (!window.confirm(`Permanently delete "${item.name}"? This cannot be undone.`)) return;
    await trashApi.permanentlyDelete(item.id);
    await load();
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <h2 className="mb-6 text-lg font-semibold text-ink">Trash</h2>
      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-sm text-slate-400">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Deleted</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-ink">
                    {item.type === "folder" ? "📁" : "📄"} {item.name}
                  </td>
                  <td className="px-4 py-3 capitalize text-slate-500">{item.type}</td>
                  <td className="px-4 py-3 text-slate-500">{formatDate(item.deleted_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-3">
                      <Button variant="secondary" onClick={() => restore(item)}>
                        Restore
                      </Button>
                      <Button variant="danger" onClick={() => permanentlyDelete(item)}>
                        Delete forever
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-sm text-slate-400">
                    Trash is empty.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
