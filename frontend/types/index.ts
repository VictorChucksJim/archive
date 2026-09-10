export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  last_login_at: string | null;
}

export interface Folder {
  id: string;
  parent_id: string | null;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ArchiveFile {
  id: string;
  folder_id: string | null;
  name: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  checksum: string | null;
  status: "pending" | "completed";
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface TrashItem {
  id: string;
  type: "file" | "folder";
  name: string;
  deleted_at: string;
}

export interface StorageUsage {
  used_bytes: number;
  quota_bytes: number;
  remaining_bytes: number;
}

export interface UploadUrlResponse {
  file_id: string;
  upload_url: string;
  storage_key: string;
  method: string;
  expires_in: number;
  required_headers: Record<string, string>;
}
