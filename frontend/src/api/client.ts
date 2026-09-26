const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      // Required by the backend on unsafe methods in production (CSRF
      // defense); harmless everywhere else.
      "X-Requested-With": "fetch",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  putFile: <T>(path: string, file: File) =>
    request<T>(path, { method: "PUT", body: file, headers: { "Content-Type": file.type || "application/octet-stream" } }),
};

/** The backend hands back either an absolute URL (Spotify/Google photo) or
 *  a path on itself ("/users/5/avatar") for uploaded pictures. */
export function assetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  return path.startsWith("/") ? `${API_BASE}${path}` : path;
}

export const spotifyLoginUrl = `${API_BASE}/auth/spotify/login`;
export const googleLoginUrl = `${API_BASE}/auth/google/login`;
