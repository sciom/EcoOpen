export const API_BASE_EVENT = 'api-base-changed'
export const AUTH_EVENT = 'auth-changed'

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const TOKEN_KEY = 'authToken'
const EMAIL_KEY = 'authEmail'

export function getApiBase() {
  try {
    const v = localStorage.getItem('apiBase')
    return (v && v.trim()) ? v.trim() : DEFAULT_API_BASE
  } catch (_) {
    return DEFAULT_API_BASE
  }
}

export function setApiBase(url) {
  try {
    if (!url || !url.trim()) {
      localStorage.removeItem('apiBase')
    } else {
      localStorage.setItem('apiBase', url.trim())
    }
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event(API_BASE_EVENT))
    }
  } catch (_) {}
}

// Auth helpers
export function getAuthToken() {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch (_) { return '' }
}
export function getAuthEmail() {
  try { return localStorage.getItem(EMAIL_KEY) || '' } catch (_) { return '' }
}
export function isAuthenticated() {
  return !!getAuthToken()
}
function setAuth(token, email) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY)
    if (email) localStorage.setItem(EMAIL_KEY, email); else localStorage.removeItem(EMAIL_KEY)
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  } catch (_) {}
}
export function logout() { setAuth('', '') }

export async function register(email, password) {
  const base = getApiBase()
  const r = await fetch(`${base}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  // Auto-login after successful register
  await login(email, password)
  return { ok: true }
}

export async function login(email, password) {
  const base = getApiBase()
  const r = await fetch(`${base}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  const data = await r.json()
  const token = data?.access_token || ''
  if (!token) throw new Error('Invalid login response')
  setAuth(token, email)
  return { ok: true }
}

function authHeaders() {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function getHealth() {
  const base = getApiBase()
  const r = await fetch(`${base}/health`)
  if (!r.ok) {
    const body = await r.text().catch(() => '')
    throw new Error(`Health check failed: ${r.status} ${r.statusText}${body ? ' - ' + body : ''}`)
  }
  return r.json()
}

export async function getConfig() {
  const base = getApiBase()
  const r = await fetch(`${base}/config`)
  if (!r.ok) {
    const body = await r.text().catch(() => '')
    throw new Error(`Config fetch failed: ${r.status} ${r.statusText}${body ? ' - ' + body : ''}`)
  }
  return r.json()
}

function friendlyErrorText(status, rawText) {
  try {
    const parsed = JSON.parse(rawText)
    const detail = parsed?.detail || parsed?.message || rawText
    if (typeof detail === 'string') {
      if (status === 401) {
        return 'Authentication required or token invalid. Please login again in Settings.'
      }
      if (status === 503 && /Mongo dependencies|Mongo deps|requires Mongo|python-jose/i.test(detail)) {
        return `${detail}\n\nTip: Use single analyze (sync) where possible or install missing dependencies (motor, pymongo, python-jose).`
      }
      return detail
    }
    if (parsed?.detail?.code === 'embed_model_missing') {
      const model = parsed?.detail?.model || parsed?.model || ''
      const base = `Embedding model not available${model ? ': ' + model : ''}.`
      const fix = model ? `\n\nHow to fix: run: ollama pull ${model}` : ''
      return `${base}${fix}`
    }
  } catch (_) {}
  if (rawText && typeof rawText === 'string') return rawText
  return `Request failed with status ${status}`
}

export async function analyzeSingle(file) {
  const base = getApiBase()
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`${base}/analyze?mode=sync`, { method: 'POST', body: fd, headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  return r.json()
}

export async function analyzeBatch(files) {
  const base = getApiBase()
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const r = await fetch(`${base}/analyze/batch`, { method: 'POST', body: fd, headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  return r.json()
}

export async function getJob(jobId) {
  const base = getApiBase()
  const r = await fetch(`${base}/jobs/${jobId}`, { headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  return r.json()
}

export async function getTasks(params = {}) {
  const base = getApiBase()
  const qp = new URLSearchParams()
  if (params.status) qp.set('status', params.status)
  if (params.limit) qp.set('limit', String(params.limit))
  const url = qp.toString() ? `${base}/tasks/?${qp.toString()}` : `${base}/tasks/`
  const r = await fetch(url, { headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  return r.json()
}

export async function getTaskDetail(jobId) {
  const base = getApiBase()
  const r = await fetch(`${base}/tasks/${jobId}`, { headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  return r.json()
}

export async function cancelTask(jobId) {
  const base = getApiBase()
  const r = await fetch(`${base}/tasks/${jobId}/cancel`, { method: 'POST', headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  return r.json()
}

export async function exportCsv(jobId) {
  const base = getApiBase()
  const r = await fetch(`${base}/export/csv/${jobId}`, { headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = `analysis_${jobId}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } finally {
    URL.revokeObjectURL(url)
  }
}
