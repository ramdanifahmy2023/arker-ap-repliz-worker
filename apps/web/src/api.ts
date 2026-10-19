let csrf = "";
export function setCsrf(value?: string) {
  csrf = value || "";
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: unknown,
  ) {
    super(message);
  }
}
export async function api<T = Record<string, any>>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-CSRF-Token", csrf);
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(
      "Layanan kontrol tidak dapat dihubungi. Periksa koneksi dan jalankan API.",
      0,
      "offline",
    );
  }
  const data = await response
    .json()
    .catch(() => ({ detail: "Respons layanan tidak dapat dibaca." }));
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("arker-session-expired"));
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : "Permintaan belum dapat diproses.",
      response.status,
      data.code,
      data,
    );
  }
  return data as T;
}
export const post = <T = Record<string, any>>(path: string, data: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(data) });
export const put = <T = Record<string, any>>(path: string, data: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(data) });
