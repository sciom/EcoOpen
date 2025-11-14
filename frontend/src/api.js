export const API_BASE_EVENT = 'api-base-changed'
export const AUTH_EVENT = 'auth-changed'

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || '/api'
const TOKEN_KEY = 'authToken'
const EMAIL_KEY = 'authEmail'
const IS_ADMIN_KEY = 'authIsAdmin'
const USER_ID_KEY = 'authUserId'

export function getApiBase() {
  try {
    const v = localStorage.getItem('apiBase')
    const trimmed = (v && v.trim()) ? v.trim() : ''
    if (trimmed) {
      try {
        if (typeof window !== 'undefined' && window.location && window.location.protocol === 'https:') {
          // Auto-reset stale localhost override when running over HTTPS (production)
          const isLocalhost = /^http:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?(\/|$)/i.test(trimmed)
          if (isLocalhost) {
            localStorage.removeItem('apiBase')
            try { if (typeof window !== 'undefined') window.dispatchEvent(new Event(API_BASE_EVENT)) } catch (_) {}
            return DEFAULT_API_BASE
          }
        }
      } catch (_) {}
      return trimmed
    }
    return DEFAULT_API_BASE
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
export function getIsAdmin() {
  try { return localStorage.getItem(IS_ADMIN_KEY) === '1' } catch (_) { return false }
}
export function getAuthUserId() {
  try { return localStorage.getItem(USER_ID_KEY) || '' } catch (_) { return '' }
}
export function isAuthenticated() {
  return !!getAuthToken()
}
function setAuth(token, email) {
  try {
    // Clear existing state first
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(EMAIL_KEY)
    localStorage.removeItem(IS_ADMIN_KEY)
    localStorage.removeItem(USER_ID_KEY)
    
    // Set new state if token is provided
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
      if (email) localStorage.setItem(EMAIL_KEY, email)
    }
    
    // Dispatch event to notify components
    if (typeof window !== 'undefined') {
      // Use setTimeout to ensure this runs after the current execution context
      setTimeout(() => {
        window.dispatchEvent(new Event(AUTH_EVENT))
      }, 0)
    }
  } catch (error) {
    console.warn('Failed to set auth state:', error)
  }
}

export function logout() { 
  setAuth('', '') 
  // Additional cleanup to ensure clean state
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(EMAIL_KEY)
    localStorage.removeItem(IS_ADMIN_KEY)
    localStorage.removeItem(USER_ID_KEY)
  } catch (_) {}
}

export async function register(email, password, passwordConfirm) {
  const base = getApiBase()
  const r = await fetch(`${base}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, password_confirm: passwordConfirm })
  })
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  // Auto-login after successful register with a small delay to ensure server state is ready
  await new Promise(resolve => setTimeout(resolve, 100))
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
  
  // Clear any existing auth state first
  logout()
  
  // Set new auth state
  setAuth(token, email)
  
  // Sync user info with a small delay to ensure token is properly stored
  await new Promise(resolve => setTimeout(resolve, 50))
  await syncAuthMe().catch((err) => {
    console.warn('Failed to sync user info after login:', err)
    // Don't fail the login if sync fails, just log it
  })
  
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

export async function getMe() {
  const base = getApiBase()
  const r = await fetch(`${base}/auth/me`, { headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') {
      setTimeout(() => {
        window.dispatchEvent(new Event(AUTH_EVENT))
      }, 0)
    }
    throw new Error('Authentication expired')
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  return r.json()
}

export async function syncAuthMe() {
  try {
    if (!isAuthenticated()) return
    
    const me = await getMe()
    const isAdmin = !!me?.is_admin
    const userId = me?.id || me?._id || ''
    
    try {
      localStorage.setItem(IS_ADMIN_KEY, isAdmin ? '1' : '0')
      if (userId) localStorage.setItem(USER_ID_KEY, String(userId))
    } catch (error) {
      console.warn('Failed to store user metadata:', error)
    }
    
    // Dispatch event to notify components of updated user info
    if (typeof window !== 'undefined') {
      setTimeout(() => {
        window.dispatchEvent(new Event(AUTH_EVENT))
      }, 0)
    }
  } catch (error) {
    // If we can't get user info, we might have an invalid token
    console.warn('Failed to sync user info, clearing auth:', error)
    logout()
  }
}

function friendlyErrorText(status, rawText) {
  try {
    const parsed = JSON.parse(rawText)
    const detail = parsed?.detail || parsed?.message || rawText
    if (typeof detail === 'string') {
      if (status === 401) {
        return 'Authentication required or token invalid. Please login again on the Login page.'
      }
      if (status === 503 && /Mongo dependencies|Mongo deps|requires Mongo|python-jose/i.test(detail)) {
        return `${detail}\n\nTip: Install missing dependencies (motor, pymongo, python-jose) or contact your administrator.`
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
  const r = await fetch(`${base}/analyze?mode=auto`, { method: 'POST', body: fd, headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') {
      setTimeout(() => {
        window.dispatchEvent(new Event(AUTH_EVENT))
      }, 0)
    }
    throw new Error('Authentication required')
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
    if (typeof window !== 'undefined') {
      setTimeout(() => {
        window.dispatchEvent(new Event(AUTH_EVENT))
      }, 0)
    }
    throw new Error('Authentication required')
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


export async function getJobLogs(jobId, params = {}) {
  const base = getApiBase()
  const qp = new URLSearchParams()
  if (params.limit) qp.set('limit', String(params.limit))
  if (params.since) qp.set('since', String(params.since))
  if (params.order) qp.set('order', String(params.order))
  const url = qp.toString() ? `${base}/tasks/${jobId}/logs?${qp.toString()}` : `${base}/tasks/${jobId}/logs`
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

export async function downloadJobLogs(jobId, params = {}) {
  const base = getApiBase()
  const qp = new URLSearchParams()
  if (params.order) qp.set('order', String(params.order))
  const url = qp.toString() ? `${base}/tasks/${jobId}/logs/download?${qp.toString()}` : `${base}/tasks/${jobId}/logs/download`
  const r = await fetch(url, { headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EVENT))
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }

  // Determine filename from Content-Disposition if provided
  const disp = r.headers?.get && r.headers.get('Content-Disposition')
  let filename = `job_${jobId}_logs.ndjson`
  if (disp && /filename\*=utf-8''([^;]+)|filename="?([^";]+)"?/i.test(disp)) {
    const m = disp.match(/filename\*=utf-8''([^;]+)|filename="?([^";]+)"?/i)
    const raw = decodeURIComponent(m[1] || m[2] || '')
    if (raw) filename = raw
  }

  let blob = await r.blob()
  if (!blob || blob.size === 0) {
    // Fallback: create a placeholder NDJSON so users still get a file
    const placeholder = `{"job_id":"${jobId}","info":"no logs available"}\n`
    blob = new Blob([placeholder], { type: 'application/x-ndjson' })
  }

  const urlObj = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = urlObj
    a.download = filename
    a.rel = 'noopener'
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } finally {
    URL.revokeObjectURL(urlObj)
  }
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

export async function rerunTask(jobId) {
  const base = getApiBase()
  const r = await fetch(`${base}/tasks/${jobId}/rerun`, { method: 'POST', headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') {
      setTimeout(() => {
        window.dispatchEvent(new Event(AUTH_EVENT))
      }, 0)
    }
  }
  if (!r.ok) {
    const t = await r.text().catch(() => '')
    throw new Error(friendlyErrorText(r.status, t))
  }
  return r.json()
}

export async function deleteTask(jobId) {
  const base = getApiBase()
  const r = await fetch(`${base}/tasks/${jobId}/delete`, { method: 'POST', headers: { ...authHeaders() } })
  if (r.status === 401) {
    logout()
    if (typeof window !== 'undefined') {
      setTimeout(() => {
        window.dispatchEvent(new Event(AUTH_EVENT))
      }, 0)
    }
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
