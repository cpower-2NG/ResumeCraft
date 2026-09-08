const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || '请求失败')
  }
  return response.json()
}

export const post = <T>(path: string, body?: unknown) => api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
