"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { files as filesApi, folders as foldersApi, search as searchApi, sha256Hex, ApiError } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";
import { Button, ErrorBanner, Input } from "@/components/ui";
import type { ArchiveFile, Folder } from "@/types";

type SortKey = "name" | "size_bytes" | "updated_at";

interface UploadTask {
  id: string;
  filename: string;
  progress: number;
  status: "uploading" | "done" | "error";
  error?: string;
}

export function FileManager({ folderId }: { folderId: string | null }) {
  const router = useRouter();
  const [folders, setFolders] = useState<Folder[]>([]);
  const [files, setFiles] = useState<ArchiveFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("updated_at");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ files: ArchiveFile[]; folders: Folder[] } | null>(null);
  const [uploads, setUploads] = useState<UploadTask[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [newFolderOpen, setNewFolderOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [f, fl] = await Promise.all([foldersApi.list(folderId), filesApi.list(folderId)]);
      setFolders(f);
      setFiles(fl);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load your archive.");
    } finally {
      setLoading(false);
    }
  }, [folderId]);

  useEffect(() => {
    load();
  }, [load]);

  // ---- Search ----
  useEffect(() => {
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }
    const handle = setTimeout(() => {
      searchApi.query(query.trim()).then(setSearchResults).catch(() => setSearchResults(null));
    }, 300);
    return () => clearTimeout(handle);
  }, [query]);

  // ---- Upload ----
  const uploadFile = useCallback(
    async (file: File) => {
      const taskId = `${file.name}-${Date.now()}-${Math.random()}`;
      setUploads((prev) => [...prev, { id: taskId, filename: file.name, progress: 0, status: "uploading" }]);

      try {
        const mimeType = file.type || "application/octet-stream";
        const presigned = await filesApi.requestUploadUrl(file.name, mimeType, file.size, folderId);

        await filesApi.uploadToStorage(presigned.upload_url, file, presigned.required_headers, (pct) => {
          setUploads((prev) => prev.map((u) => (u.id === taskId ? { ...u, progress: pct } : u)));
        });

        const checksum = await sha256Hex(file);
        await filesApi.complete(presigned.file_id, checksum);

        setUploads((prev) => prev.map((u) => (u.id === taskId ? { ...u, progress: 100, status: "done" } : u)));
        await load();
      } catch (err) {
        const message = err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Upload failed";
        setUploads((prev) => prev.map((u) => (u.id === taskId ? { ...u, status: "error", error: message } : u)));
      }
    },
    [folderId, load]
  );

  function handleFilesSelected(fileList: FileList | null) {
    if (!fileList) return;
    Array.from(fileList).forEach(uploadFile);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    handleFilesSelected(e.dataTransfer.files);
  }

  async function retryUpload(task: UploadTask) {
    setUploads((prev) => prev.filter((u) => u.id !== task.id));
    // Retrying requires the original File object, which we don't retain
    // once dismissed; simplest correct UX is prompting a fresh selection.
    fileInputRef.current?.click();
  }

  // ---- Folder / file actions ----
  async function createFolder() {
    if (!newFolderName.trim()) return;
    try {
      await foldersApi.create(newFolderName.trim(), folderId);
      setNewFolderName("");
      setNewFolderOpen(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create folder.");
    }
  }

  async function renameFile(file: ArchiveFile) {
    const name = window.prompt("Rename file", file.name);
    if (!name || name === file.name) return;
    await filesApi.rename(file.id, name);
    await load();
  }

  async function renameFolder(folder: Folder) {
    const name = window.prompt("Rename folder", folder.name);
    if (!name || name === folder.name) return;
    await foldersApi.rename(folder.id, name);
    await load();
  }

  async function deleteFile(file: ArchiveFile) {
    if (!window.confirm(`Move "${file.name}" to Trash?`)) return;
    await filesApi.remove(file.id);
    await load();
  }

  async function deleteFolder(folder: Folder) {
    if (!window.confirm(`Move "${folder.name}" to Trash?`)) return;
    await foldersApi.remove(folder.id);
    await load();
  }

  async function downloadFile(file: ArchiveFile) {
    const { download_url } = await filesApi.downloadUrl(file.id);
    window.open(download_url, "_blank");
  }

  const sortedFiles = [...files].sort((a, b) => {
    if (sortKey === "name") return a.name.localeCompare(b.name);
    if (sortKey === "size_bytes") return b.size_bytes - a.size_bytes;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });

  const displayFolders = searchResults ? searchResults.folders : folders;
  const displayFiles = searchResults ? searchResults.files : sortedFiles;

  return (
    <div
      className="flex-1 overflow-y-auto p-8"
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <Input
          placeholder="Search your archive…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="max-w-xs"
        />
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setNewFolderOpen((v) => !v)}>
            New folder
          </Button>
          <Button onClick={() => fileInputRef.current?.click()}>Upload</Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              handleFilesSelected(e.target.files);
              e.target.value = "";
            }}
          />
        </div>
      </div>

      {newFolderOpen && (
        <div className="mb-4 flex max-w-sm gap-2">
          <Input
            autoFocus
            placeholder="Folder name"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createFolder()}
          />
          <Button onClick={createFolder}>Create</Button>
        </div>
      )}

      <ErrorBanner message={error} />

      {uploads.length > 0 && (
        <div className="mb-6 space-y-2">
          {uploads.map((task) => (
            <div key={task.id} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm">
              <span className="flex-1 truncate">{task.filename}</span>
              {task.status === "uploading" && (
                <div className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full bg-accent transition-all" style={{ width: `${task.progress}%` }} />
                </div>
              )}
              {task.status === "done" && <span className="text-green-600">Uploaded</span>}
              {task.status === "error" && (
                <>
                  <span className="text-red-600">{task.error || "Failed"}</span>
                  <button className="text-accent underline" onClick={() => retryUpload(task)}>
                    Retry
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {isDragging && (
        <div className="mb-6 flex h-24 items-center justify-center rounded-lg border-2 border-dashed border-accent bg-blue-50 text-sm text-accent">
          Drop files to upload
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-400">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th
                  className="cursor-pointer px-4 py-3 font-medium"
                  onClick={() => setSortKey("size_bytes")}
                >
                  Size
                </th>
                <th
                  className="cursor-pointer px-4 py-3 font-medium"
                  onClick={() => setSortKey("updated_at")}
                >
                  Modified
                </th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayFolders.map((folder) => (
                <tr key={folder.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <button
                      className="flex items-center gap-2 font-medium text-ink hover:text-accent"
                      onClick={() => router.push(`/dashboard/folder/${folder.id}`)}
                    >
                      📁 {folder.name}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-slate-500">Folder</td>
                  <td className="px-4 py-3 text-slate-500">—</td>
                  <td className="px-4 py-3 text-slate-500">{formatDate(folder.updated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-3 text-xs">
                      <button className="text-accent hover:underline" onClick={() => renameFolder(folder)}>
                        Rename
                      </button>
                      <button className="text-red-600 hover:underline" onClick={() => deleteFolder(folder)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}

              {displayFiles.map((file) => (
                <tr key={file.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-ink">📄 {file.name}</td>
                  <td className="px-4 py-3 text-slate-500">{file.mime_type}</td>
                  <td className="px-4 py-3 text-slate-500">{formatBytes(file.size_bytes)}</td>
                  <td className="px-4 py-3 text-slate-500">{formatDate(file.updated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-3 text-xs">
                      <button className="text-accent hover:underline" onClick={() => downloadFile(file)}>
                        Download
                      </button>
                      <button className="text-accent hover:underline" onClick={() => renameFile(file)}>
                        Rename
                      </button>
                      <button className="text-red-600 hover:underline" onClick={() => deleteFile(file)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}

              {displayFolders.length === 0 && displayFiles.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-sm text-slate-400">
                    {searchResults ? "No matches found." : "This folder is empty. Upload a file to get started."}
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
