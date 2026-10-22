// A thin JSON client for the backend. Errors carry the server's message so views can show it as is.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** the parsed error body, e.g. the newer copy of an item on a 409 */
    public body: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ValidationIssue {
  msg?: string;
  loc?: (string | number)[];
}

/** Turn a FastAPI error body into one readable sentence. */
export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as ValidationIssue;
    const field = first.loc?.filter((p) => p !== "body").join(".");
    return field ? `Check ${field}: ${first.msg ?? "invalid value"}` : (first.msg ?? "Check the form.");
  }
  if (status === 0) return "Quarry could not reach the server. Check your connection.";
  if (status >= 500) return "Something went wrong on the server. Try again in a moment.";
  return `Request failed (${status}).`;
}

export async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, errorMessage(0, null));
  }
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, errorMessage(res.status, data), data);
  return data as T;
}

export const get = <T>(path: string) => api<T>("GET", path);
export const post = <T>(path: string, body?: unknown) => api<T>("POST", path, body ?? {});
export const patch = <T>(path: string, body: unknown) => api<T>("PATCH", path, body);
export const put = <T>(path: string, body: unknown) => api<T>("PUT", path, body);
export const del = <T>(path: string, body?: unknown) => api<T>("DELETE", path, body);
