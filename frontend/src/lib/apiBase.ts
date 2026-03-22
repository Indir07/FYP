/**
 * API URL helper. In local dev, leave VITE_API_BASE_URL unset so requests use
 * same-origin paths like `/api/...` (Vite proxies to the backend — avoids CORS).
 * For production or Docker, set VITE_API_BASE_URL to your public API origin.
 */
export function apiUrl(path: string): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  const base = (raw ?? '').trim().replace(/\/$/, '')
  const p = path.startsWith('/') ? path : `/${path}`
  return base ? `${base}${p}` : p
}

/** Parse FastAPI error body into a single message */
export function formatApiErrorBody(data: unknown): string {
  if (!data || typeof data !== 'object') return 'Request failed'
  const detail = (data as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: string; loc?: unknown }) => {
        if (item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string') {
          return item.msg
        }
        return JSON.stringify(item)
      })
      .join('; ')
  }
  return 'Request failed'
}

export function networkErrorMessage(err: unknown): string {
  if (err instanceof Error) {
    if (err.name === 'AbortError') {
      return 'Request timed out. Check that the backend is running and try again.'
    }
    if (err.message === 'Failed to fetch' || err.message.includes('NetworkError')) {
      return 'Cannot reach the API. Start the backend (port 8000), restart the dev server, and open the URL Vite prints (e.g. http://localhost:5173 or :5174 if 5173 is in use).'
    }
    return err.message
  }
  return 'Request failed'
}
