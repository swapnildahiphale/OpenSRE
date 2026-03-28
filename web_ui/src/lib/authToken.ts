const TOKEN_KEY = "opensre_token";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}


