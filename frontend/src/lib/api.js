const defaultBase = window.location.port === "5173" ? "http://localhost:8000" : "/api";
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || defaultBase).replace(/\/$/, "");

export function getToken() {
  return localStorage.getItem("adbothost_token");
}

export function setToken(token) {
  if (token) localStorage.setItem("adbothost_token", token);
  else localStorage.removeItem("adbothost_token");
}

export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // keep default message
    }
    throw new Error(message);
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return response.text();
  return response.json();
}
