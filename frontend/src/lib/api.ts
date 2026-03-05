const API_BASE = import.meta.env.VITE_API_URL;

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = sessionStorage.getItem("google_access_token");
  if (!token) throw new Error("NO_TOKEN");

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (res.status === 401 || res.status === 403) {
    sessionStorage.removeItem("google_access_token");
    throw new Error("TOKEN_EXPIRED");
  }

  return res;
}
