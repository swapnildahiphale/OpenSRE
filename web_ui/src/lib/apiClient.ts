export async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});

  // Default JSON accept for our API routes
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  return fetch(path, { ...init, headers });
}


