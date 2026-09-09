const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isForm = options.body instanceof FormData
  const response = await fetch(`${BASE}${path}`, { ...options, headers: { ...(isForm ? {} : { 'Content-Type': 'application/json' }), ...options.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || '请求失败')
  }
  return response.json()
}

export const post = <T>(path: string, body?: unknown) => api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
export const del = <T>(path: string) => api<T>(path, { method: 'DELETE' })
export const upload = <T>(path: string, body: FormData) => api<T>(path, { method: 'POST', body })
