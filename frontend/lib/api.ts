import {
  AdminSettings,
  AssetBrowseResponse,
  AssetDetail,
  AssetListResponse,
  AuditLogEntry,
  AuthUser,
  CollectionDetail,
  CollectionSummary,
  CompareResponse,
  GroupSummary,
  ResetResponse,
  ScanJob,
  ScanJobErrorEntry,
  SearchFilters,
  SimilarAsset,
  Source,
  SourceBrowseInspect,
  SourceBrowseResponse,
  SourceTreeResponse,
  SourceUploadResponse,
  TagCount,
  UserRole,
  UserStatus,
  UserSummary,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error("Unexpected response from server.");
  }
  return (await response.json()) as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const body = response.headers.get("content-type")?.includes("application/json")
      ? await response.json()
      : null;
    throw new Error(body?.detail ?? "Request failed.");
  }

  return parseResponse<T>(response);
}

function buildQuery<T extends object>(filters: T): string {
  const params = new URLSearchParams();
  Object.entries(filters as Record<string, string | number | boolean | null | undefined>).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, String(value));
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function mediaUrl(path: string | null): string | null {
  return path ? `${API_BASE_URL}${path}` : null;
}

export function assetImageUrl(id: string, options: { w?: number; h?: number; quality?: number; fmt?: "webp" | "jpeg" } = {}) {
  return `${API_BASE_URL}/assets/${id}/image${buildQuery(options)}`;
}

export function login(username: string, password: string) {
  return request<AuthUser>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function logout() {
  return request<void>("/auth/logout", { method: "POST" });
}

export function fetchMe() {
  return request<AuthUser>("/auth/me");
}

export function changePassword(payload: { current_password: string; new_password: string; confirm_password: string }) {
  return request<void>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchSources() {
  return request<Source[]>("/sources");
}

export function fetchSource(id: string) {
  return request<Source>(`/sources/${id}`);
}

export function createSource(payload: { name: string; root_path: string; type: string }) {
  return request<Source>("/sources", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchSourceBrowse(id: string, path = "") {
  const query = path ? `?path=${encodeURIComponent(path)}` : "";
  return request<SourceBrowseResponse>(`/sources/${id}/browse${query}`);
}

export function fetchSourceInspect(id: string, path: string) {
  return request<SourceBrowseInspect>(`/sources/${id}/browse/inspect?path=${encodeURIComponent(path)}`);
}

export function fetchSourceTree(id: string, path = "") {
  const query = path ? `?path=${encodeURIComponent(path)}` : "";
  return request<SourceTreeResponse>(`/sources/${id}/tree${query}`);
}

export function deleteSource(id: string) {
  return request<void>(`/sources/${id}`, { method: "DELETE" });
}

export function triggerScan(id: string) {
  return request<ScanJob>(`/sources/${id}/scan`, { method: "POST" });
}

export function fetchScanJobs() {
  return request<ScanJob[]>("/scan-jobs");
}

export function fetchScanJob(id: string) {
  return request<ScanJob>(`/scan-jobs/${id}`);
}

export function fetchScanJobErrors(id: string) {
  return request<ScanJobErrorEntry[]>(`/scan-jobs/${id}/errors`);
}

export function cancelScanJob(id: string) {
  return request<ScanJob>(`/scan-jobs/${id}/cancel`, { method: "POST" });
}

export function fetchAssets(filters: SearchFilters = {}) {
  return request<AssetListResponse>(`/assets${buildQuery(filters)}`);
}

export function fetchAssetBrowse(filters: { source_id?: string; sort?: string; page?: number; page_size?: number } = {}) {
  const query = buildQuery(filters);
  return request<AssetBrowseResponse>(`/assets/browse${query}`);
}

export function fetchAsset(id: string) {
  return request<AssetDetail>(`/assets/${id}`);
}

export function fetchSearch(filters: SearchFilters = {}) {
  return request<AssetListResponse>(`/search${buildQuery(filters)}`);
}

export function fetchTags() {
  return request<TagCount[]>("/tags");
}

export function fetchTagAssets(tag: string, page = 1, pageSize = 24) {
  return request<AssetListResponse>(`/tags/${encodeURIComponent(tag)}/assets?page=${page}&page_size=${pageSize}`);
}

export function fetchSimilar(id: string, type: "duplicate" | "semantic" | "tag", limit = 50) {
  return request<SimilarAsset[]>(`/assets/${id}/similar?type=${type}&limit=${limit}`);
}

export function fetchSimilarByImage(id: string, limit = 24) {
  return request<SimilarAsset[]>(`/assets/${id}/search-similar-by-image?limit=${limit}`);
}

export function bulkAnnotateAssets(payload: {
  asset_ids: string[];
  rating?: number | null;
  review_status?: string | null;
  flagged?: boolean | null;
  note?: string | null;
}) {
  return request<void>("/assets/bulk-annotate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchCompare(a: string, b: string) {
  return request<CompareResponse>(`/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
}

export function submitCompareReview(assetIdA: string, assetIdB: string, action: string) {
  return request<void>("/compare/review", {
    method: "POST",
    body: JSON.stringify({ asset_id_a: assetIdA, asset_id_b: assetIdB, action }),
  });
}

export function resetApplicationData(mode: "index" | "all") {
  return request<ResetResponse>("/admin/reset", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export function fetchAdminUsers() {
  return request<UserSummary[]>("/admin/users");
}

export function createAdminUser(payload: { username: string; password: string; role: UserRole }) {
  return request<UserSummary>("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAdminUser(
  id: string,
  payload: {
    username?: string;
    role?: UserRole;
    status?: UserStatus;
    locked_until?: string | null;
    ban_reason?: string | null;
    group_ids?: string[];
  }
) {
  return request<UserSummary>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteAdminUser(id: string) {
  return request<void>(`/admin/users/${id}`, { method: "DELETE" });
}

export function fetchGroups() {
  return request<GroupSummary[]>("/admin/groups");
}

// Aliases used by /admin/groups and /admin/users pages
export const fetchAdminGroups = fetchGroups;

export function createGroup(payload: { name: string; description: string; permissions: Record<string, unknown> }) {
  return request<GroupSummary>("/admin/groups", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export const createAdminGroup = createGroup;

export function updateGroup(id: string, payload: { name?: string; description?: string; permissions?: Record<string, unknown> }) {
  return request<GroupSummary>(`/admin/groups/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export const updateAdminGroup = updateGroup;

export function deleteGroup(id: string) {
  return request<void>(`/admin/groups/${id}`, { method: "DELETE" });
}

export const deleteAdminGroup = deleteGroup;

export function resetAdminUserPassword(id: string, newPassword: string) {
  return request<void>(`/admin/users/${id}/password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export function fetchAuditLogs(limit = 50) {
  return request<AuditLogEntry[]>(`/admin/audit-logs?limit=${limit}`);
}

export function fetchAdminSettings() {
  return request<AdminSettings>("/admin/settings");
}

export function updateAdminSettings(payload: AdminSettings) {
  return request<AdminSettings>("/admin/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function rebuildTagSimilarity() {
  return request<{ rebuilt_assets: number; rebuilt_links: number }>("/admin/settings/rebuild-tag-similarity", {
    method: "POST",
  });
}

export async function restoreBackup(file: File, options: { dryRun?: boolean; confirm?: string } = {}) {
  const query = buildQuery({
    dry_run: options.dryRun ?? false,
    confirm: options.confirm ?? "",
  });
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/admin/restore${query}`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!response.ok) {
    const body = response.headers.get("content-type")?.includes("application/json")
      ? await response.json()
      : null;
    throw new Error(body?.detail ?? "Restore failed.");
  }
  return parseResponse<Record<string, unknown>>(response);
}

export function purgeDeepzoom() {
  return request<{ deleted_tile_directories: number; deleted_manifests: number }>("/admin/purge-deepzoom", {
    method: "POST",
  });
}

export function reindexSearch() {
  return request<{ rebuilt_assets: number }>("/admin/reindex-search", {
    method: "POST",
  });
}

export function fetchCollections() {
  return request<CollectionSummary[]>("/collections");
}

export function createCollection(payload: { name: string; description: string }) {
  return request<CollectionSummary>("/collections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchCollection(id: string, page = 1, pageSize = 36) {
  return request<CollectionDetail>(`/collections/${id}?page=${page}&page_size=${pageSize}`);
}

export function updateCollection(id: string, payload: { name?: string; description?: string }) {
  return request<CollectionSummary>(`/collections/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteCollection(id: string) {
  return request<void>(`/collections/${id}`, { method: "DELETE" });
}

export function addAssetsToCollection(id: string, assetIds: string[]) {
  return request<CollectionDetail>(`/collections/${id}/assets`, {
    method: "POST",
    body: JSON.stringify({ asset_ids: assetIds }),
  });
}

export function addSearchResultsToCollection(
  id: string,
  payload: {
    q?: string;
    media_type?: string;
    camera_make?: string;
    camera_model?: string;
    year?: number;
    width_min?: number;
    width_max?: number;
    height_min?: number;
    height_max?: number;
    duration_min?: number;
    duration_max?: number;
    tags?: string[];
  }
) {
  return request<CollectionDetail>(`/collections/${id}/search-results`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function removeAssetFromCollection(id: string, assetId: string) {
  return request<void>(`/collections/${id}/assets/${assetId}`, { method: "DELETE" });
}

export async function uploadToSource(id: string, files: File[], folder = "") {
  const formData = new FormData();
  if (folder.trim()) {
    formData.append("folder", folder.trim());
  }
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`${API_BASE_URL}/sources/${id}/upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!response.ok) {
    const body = response.headers.get("content-type")?.includes("application/json")
      ? await response.json()
      : null;
    throw new Error(body?.detail ?? "Upload failed.");
  }
  return parseResponse<SourceUploadResponse>(response);
}
