import type {
  ArchiveFile,
  Folder,
  StorageUsage,
  TrashItem,
  UploadUrlResponse,
  User,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include", // send/receive the httpOnly session cookie
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return (await res.json()) as T;
}

// ---------- Auth ----------

export const auth = {
  register: (email: string, password: string, display_name: string) =>
    request<User>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  me: () => request<User>("/api/auth/me"),
};

// ---------- Folders ----------

export const folders = {
  list: (parentId?: string | null) =>
    request<Folder[]>(`/api/folders${parentId ? `?parent_id=${parentId}` : ""}`),
  create: (name: string, parent_id?: string | null) =>
    request<Folder>("/api/folders", {
      method: "POST",
      body: JSON.stringify({ name, parent_id: parent_id ?? null }),
    }),
  rename: (id: string, name: string) =>
    request<Folder>(`/api/folders/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  remove: (id: string) => request<void>(`/api/folders/${id}`, { method: "DELETE" }),
};

// ---------- Files ----------

export const files = {
  list: (folderId?: string | null) =>
    request<ArchiveFile[]>(`/api/files${folderId ? `?folder_id=${folderId}` : ""}`),

  requestUploadUrl: (filename: string, mime_type: string, size_bytes: number, folder_id?: string | null) =>
    request<UploadUrlResponse>("/api/files/upload-url", {
      method: "POST",
      body: JSON.stringify({ filename, mime_type, size_bytes, folder_id: folder_id ?? null }),
    }),

  /** Uploads directly to object storage using the presigned URL -- the
   * file bytes never pass through our own backend. */
  uploadToStorage: (
    uploadUrl: string,
    file: File,
    headers: Record<string, string>,
    onProgress?: (pct: number) => void
  ): Promise<void> =>
    new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", uploadUrl);
      Object.entries(headers).forEach(([k, v]) => xhr.setRequestHeader(k, v));
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable && onProgress) {
          onProgress(Math.round((evt.loaded / evt.total) * 100));
        }
      };
      xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload failed (${xhr.status})`)));
      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.send(file);
    }),

  complete: (file_id: string, checksum: string) =>
    request<ArchiveFile>("/api/files/complete", {
      method: "POST",
      body: JSON.stringify({ file_id, checksum }),
    }),

  rename: (id: string, name: string) =>
    request<ArchiveFile>(`/api/files/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),

  move: (id: string, folder_id: string | null) =>
    request<ArchiveFile>(`/api/files/${id}`, { method: "PATCH", body: JSON.stringify({ folder_id }) }),

  remove: (id: string) => request<void>(`/api/files/${id}`, { method: "DELETE" }),

  downloadUrl: (id: string) => request<{ download_url: string; expires_in: number }>(`/api/files/${id}/download-url`),
};

// ---------- Trash ----------

export const trash = {
  list: () => request<TrashItem[]>("/api/trash"),
  restore: (id: string) => request<{ id: string; type: string; restored: boolean }>(`/api/trash/${id}/restore`, { method: "POST" }),
  permanentlyDelete: (id: string) => request<void>(`/api/trash/${id}`, { method: "DELETE" }),
};

// ---------- Search ----------

export const search = {
  query: (q: string) => request<{ files: ArchiveFile[]; folders: Folder[] }>(`/api/search?q=${encodeURIComponent(q)}`),
};

// ---------- Storage usage ----------

export const storage = {
  usage: () => request<StorageUsage>("/api/storage/usage"),
};

/** Computes a SHA-256 hex checksum client-side using the Web Crypto API,
 * so the server can verify upload integrity without ever seeing the raw
 * bytes pass through it. */
export async function sha256Hex(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
