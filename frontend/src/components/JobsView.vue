<template>
  <div class="jobs-view">
    <div class="header-section">
      <h2 class="section-title">
        <i class="fas fa-list-check"></i>
        Jobs
        <span v-if="isAdmin" class="admin-badge"><i class="fas fa-shield-alt"></i> Admin</span>
      </h2>
      <p class="section-description">
        Monitor and manage your recent and running analyses.
      </p>
    </div>

    <div class="controls-row">
      <div class="filters">
        <label class="filter-label">
          <i class="fas fa-filter"></i>
          Status
        </label>
        <select v-model="status" class="filter-select">
          <option value="">All</option>
          <option value="running">Running</option>
          <option value="pending">Pending</option>
          <option value="done">Done</option>
          <option value="error">Error</option>
        </select>
        <label class="filter-label">
          <i class="fas fa-hashtag"></i>
          Limit
        </label>
        <input v-model.number="limit" type="number" min="1" max="200" class="filter-input" />
        <button @click="manualRefresh" :disabled="loading" class="refresh-button">
          <i :class="loading ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i>
          Refresh
        </button>
      </div>
      <div class="legend">
        <span class="legend-item running"><i class="fas fa-spinner"></i> Running</span>
        <span class="legend-item done"><i class="fas fa-check-circle"></i> Done</span>
        <span class="legend-item error"><i class="fas fa-exclamation-circle"></i> Error</span>
        <span class="legend-item pending"><i class="fas fa-clock"></i> Pending</span>
      </div>
    </div>

    <div v-if="error" class="error-message">
      <i class="fas fa-exclamation-circle"></i>
      {{ error }}
    </div>

    <div class="jobs-card">
      <div class="jobs-header">
        <h3><i class="fas fa-tasks"></i> Recent Jobs</h3>
        <div class="auto-refresh">
          <label>
            <input type="checkbox" v-model="autoRefresh" />
            Auto-refresh
          </label>
          <span class="muted">every {{ refreshMs/1000 }}s</span>
        </div>
      </div>

      <div v-if="!jobs.length && !loading" class="empty-state">
        <i class="fas fa-inbox"></i>
        <p>No jobs found. Start a batch to see it here.</p>
      </div>

      <div class="jobs-list" v-else>
        <div v-for="j in jobs" :key="j.job_id" class="job-row" :class="j.status">
          <div class="job-main">
            <div class="job-status" :class="j.status">
              <i :class="statusIcon(j.status)"></i>
              <span class="status-text">{{ statusText(j.status) }}</span>
            </div>
            <div class="job-meta">
              <div class="meta-line">
                <span class="label">Job ID:</span>
                <span class="value mono">{{ j.job_id }}</span>
              </div>
              <div class="meta-line">
                <span class="label">Progress:</span>
                <span class="value">{{ j.progress?.current || 0 }} / {{ j.progress?.total || 0 }}</span>
              </div>
              <div class="meta-line" v-if="isAdmin && (j.created_by?.email || j.created_by?.user_id)">
                <span class="label">Created by:</span>
                <span class="value">
                  <template v-if="j.created_by?.email">{{ j.created_by.email }}</template>
                  <template v-else-if="j.created_by?.user_id">user {{ j.created_by.user_id }}</template>
                </span>
              </div>
              <div class="meta-line" v-if="j.created_at">
                <span class="label">Created:</span>
                <span class="value">{{ fmtDate(j.created_at) }}</span>
              </div>
              <div class="meta-line" v-if="j.updated_at">
                <span class="label">Updated:</span>
                <span class="value">{{ fmtDate(j.updated_at) }}</span>
              </div>
              <div class="meta-line" v-if="j.started_at">
                <span class="label">Started:</span>
                <span class="value">{{ fmtDate(j.started_at) }}</span>
              </div>
              <div class="meta-line" v-if="j.finished_at">
                <span class="label">Finished:</span>
                <span class="value">{{ fmtDate(j.finished_at) }}</span>
              </div>
              <div class="meta-line" v-if="j.duration_ms != null">
                <span class="label">Duration:</span>
                <span class="value">{{ fmtDuration(j.duration_ms) }}</span>
              </div>
            </div>
            <div class="progress">
              <div class="bar"><div class="fill" :style="{width: pct(j) + '%'}"></div></div>
              <div class="pct">{{ pct(j) }}%</div>
            </div>
          </div>
          <div class="job-actions">
            <button class="action" @click="viewDetail(j.job_id)">
              <i class="fas fa-eye"></i> View
            </button>
            <button class="action success" :disabled="j.status !== 'done'" @click="onExport(j.job_id)">
              <i class="fas fa-file-csv"></i> CSV
            </button>
            <button class="action danger" :disabled="!canCancel(j)" @click="onCancel(j.job_id)">
              <i class="fas fa-ban"></i> Cancel
            </button>
            <button v-if="isAdmin" class="action danger" @click="onDelete(j.job_id)">
              <i class="fas fa-trash"></i> Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="detail" class="detail-modal" @click.self="closeDetail()">
      <div class="detail-card">
        <div class="detail-header">
          <h3><i class="fas fa-eye"></i> Job Detail</h3>
          <button class="close" @click="closeDetail()"><i class="fas fa-times"></i></button>
        </div>
        <div class="detail-body">
          <div class="detail-meta">
            <div class="meta"><strong>Status:</strong> {{ statusText(detail.status) }}</div>
            <div class="meta"><strong>Job ID:</strong> <span class="mono">{{ detail.job_id }}</span></div>
            <div class="meta" v-if="detail.duration_ms != null"><strong>Duration:</strong> {{ fmtDuration(detail.duration_ms) }}</div>
          </div>

          <div v-if="detail.error" class="error-block">
            <i class="fas fa-exclamation-triangle"></i>
            {{ detail.error }}
          </div>

          <div v-if="detail.results && detail.results.length" class="results-list">
            <h4><i class="fas fa-list"></i> Results ({{ detail.results.length }})</h4>
            <div class="result" v-for="(r, idx) in detail.results" :key="idx">
              <div class="result-head">
                <div class="file">
                  <i class="fas fa-file-pdf"></i>
                  <span class="name">{{ r.source_file || 'unknown.pdf' }}</span>
                </div>
                <span class="badge" :class="r.error ? 'error' : 'success'">
                  <i :class="r.error ? 'fas fa-exclamation-circle' : 'fas fa-check-circle'"></i>
                  {{ r.error ? 'Error' : 'Success' }}
                </span>
              </div>
              <div v-if="r.error" class="result-error">{{ r.error }}</div>
              <div v-else class="result-fields">
                <div v-if="r.title" class="field"><strong>Title:</strong> {{ r.title }}</div>
                <div v-if="r.doi" class="field"><strong>DOI:</strong> <a :href="doiHref(r.doi)" target="_blank" rel="noopener" class="doi-link">{{ r.doi }} <i class="fas fa-external-link-alt"></i></a></div>
                <div v-if="r.data_availability_statement" class="field"><strong>Data Availability:</strong> {{ r.data_availability_statement }}</div>
                <div v-if="r.code_availability_statement" class="field"><strong>Code Availability:</strong> {{ r.code_availability_statement }}</div>
                <div v-if="r.data_sharing_license" class="field"><strong>Data License:</strong> {{ r.data_sharing_license }}</div>
                <div v-if="r.code_license" class="field"><strong>Code License:</strong> {{ r.code_license }}</div>
                <div v-if="r.data_links && r.data_links.length" class="links"><strong>Data Links:</strong>
                  <div class="links-list">
                    <a v-for="(l,i) in r.data_links" :key="'dl'+i" :href="l" target="_blank" rel="noopener" class="resource-link"><i class="fas fa-external-link-alt"></i>{{ l }}</a>
                  </div>
                </div>
                <div v-if="r.code_links && r.code_links.length" class="links"><strong>Code Links:</strong>
                  <div class="links-list">
                    <a v-for="(l,i) in r.code_links" :key="'cl'+i" :href="l" target="_blank" rel="noopener" class="resource-link"><i class="fas fa-external-link-alt"></i>{{ l }}</a>
                  </div>
                </div>
              </div>
            </div>
          </div>

           <div v-if="isAdmin" class="logs-panel">
            <div class="logs-header">
              <h4><i class="fas fa-stream"></i> Logs</h4>
              <div class="logs-controls">
                <button class="action" @click="resetLogs()"><i :class="logsLoading ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i> Refresh</button>
                <button class="action" :disabled="logsLoading || downloadingLogs || !isAdmin" @click="onDownloadLogs()">
                  <i :class="downloadingLogs ? 'fas fa-spinner fa-spin' : 'fas fa-download'"></i> {{ downloadingLogs ? 'Downloading…' : 'Download' }}
                </button>
              </div>
            </div>
            <div class="logs-preview-note">Showing last 100 lines (newest first)</div>
            <div v-if="logsError" class="error-block"><i class="fas fa-exclamation-triangle"></i> {{ logsError }}</div>
            <div class="logs-list" :class="{ loading: logsLoading }">
              <div v-if="!logs.length && !logsLoading" class="empty-state"><i class="fas fa-inbox"></i><p>No logs yet.</p></div>
              <div v-else class="log-row" v-for="(row, idx) in logs" :key="idx">
                <div class="log-left">
                  <div class="ts">{{ fmtDate(row.ts) }}</div>
                  <div class="level" :class="row.level || 'info'">{{ (row.level || 'info').toUpperCase() }}</div>
                </div>
                <div class="log-main">
                  <div class="line">
                    <span v-if="row.op" class="op">[{{ row.op }}]</span>
                    <span class="msg">{{ row.message || '' }}</span>
                    <span v-if="row.duration_ms != null" class="dur">{{ row.duration_ms }}ms</span>
                  </div>
                  <div class="meta">
                    <span v-if="row.filename" class="chip"><i class="fas fa-file"></i> {{ row.filename }}</span>
                    <span v-if="row.doc_id" class="chip mono"><i class="fas fa-hashtag"></i> {{ row.doc_id }}</span>
                  </div>
                  <details v-if="row.extra && (row.extra.error || row.extra.trace)" class="extra">
                    <summary><i class="fas fa-bug"></i> Error details</summary>
                    <pre>{{ pretty(row.extra) }}</pre>
                  </details>
                </div>
              </div>
            </div>
          </div>


          <details class="raw-json">
            <summary><i class="fas fa-code"></i> Raw JSON</summary>
            <pre>{{ pretty(detail) }}</pre>
          </details>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { getTasks, getJob, cancelTask, exportCsv, deleteTask, getJobLogs, downloadJobLogs, AUTH_EVENT, isAuthenticated, getIsAdmin, getAuthUserId, syncAuthMe } from '../api'

const jobs = ref([])
const status = ref('')
const limit = ref(50)
const loading = ref(false)
const error = ref('')
const autoRefresh = ref(true)
const refreshMs = 1200
let timer = null

  const detail = ref(null)
  const logs = ref([])
  const logsLoading = ref(false)
  const logsError = ref('')
  const downloadingLogs = ref(false)
  let logsTimer = null


function statusIcon(s) {
  switch (s) {
    case 'pending': return 'fas fa-clock'
    case 'running': return 'fas fa-spinner fa-spin'
    case 'done': return 'fas fa-check-circle'
    case 'error': return 'fas fa-exclamation-circle'
    default: return 'fas fa-question-circle'
  }
}
function statusText(s) {
  switch (s) {
    case 'pending': return 'Pending'
    case 'running': return 'Running'
    case 'done': return 'Done'
    case 'error': return 'Error'
    default: return 'Unknown'
  }
}

function pct(j) {
  const cur = j?.progress?.current || 0
  const tot = j?.progress?.total || 0
  return tot ? Math.round((cur / tot) * 100) : 0
}

function canCancel(j) {
  const terminal = j?.status !== 'running' && j?.status !== 'pending'
  if (terminal) return false
  if (isAdmin.value) return true
  const meId = getAuthUserId()
  if (j?.user_id) return String(j.user_id) === String(meId)
  return false
}

function fmtDate(v) {
  try {
    const d = new Date(v)
    if (!isFinite(d)) return String(v)
    return d.toLocaleString()
  } catch (_) { return String(v) }
}

function fmtDuration(ms) {
  const s = Math.max(0, Math.round(ms / 1000))
  const m = Math.floor(s / 60)
  const rems = s % 60
  if (m) return `${m}m ${rems}s`
  return `${rems}s`
}

async function refresh() {
  try {
    loading.value = true
    error.value = ''
    jobs.value = await getTasks({ status: status.value || undefined, limit: limit.value || undefined })
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

function manualRefresh() {
  refresh()
}

async function viewDetail(jobId) {
  try {
    const data = await getJob(jobId)
    detail.value = data
    // Reset and start fetching logs if admin
    logs.value = []
    logsError.value = ''
    if (isAdmin.value) {
      await fetchLogs()
      if (logsTimer) clearInterval(logsTimer)
      logsTimer = setInterval(() => { fetchLogs().catch(() => {}) }, 1500)
    }
  } catch (e) {
    error.value = String(e)
  }
}

async function onCancel(jobId) {
  try {
    await cancelTask(jobId)
    await refresh()
  } catch (e) {
    error.value = String(e)
  }
}

async function onExport(jobId) {
  try {
    await exportCsv(jobId)
  } catch (e) {
    error.value = String(e)
  }
}

async function onDelete(jobId) {
  try {
    if (!isAdmin.value) return
    if (!confirm('Delete this job and its files? This cannot be undone.')) return
    await deleteTask(jobId)
    await refresh()
  } catch (e) {
    error.value = String(e)
  }
}

async function onDownloadLogs() {
  try {
    if (!isAdmin.value || !detail.value || !detail.value.job_id) return
    logsError.value = ''
    downloadingLogs.value = true
    await downloadJobLogs(detail.value.job_id, { order: 'asc' })
  } catch (e) {
    logsError.value = String(e)
  } finally {
    downloadingLogs.value = false
  }
}

const authed = ref(isAuthenticated())
const isAdmin = ref(getIsAdmin())
const authUserId = ref(getAuthUserId())
function updateAuthed() { authed.value = isAuthenticated(); isAdmin.value = getIsAdmin(); authUserId.value = getAuthUserId() }

onMounted(async () => {
  window.addEventListener(AUTH_EVENT, updateAuthed)
  updateAuthed()
  await syncAuthMe().catch(() => {})
  updateAuthed()
  refresh()
  timer = setInterval(() => { if (autoRefresh.value) refresh() }, refreshMs)
})

function closeDetail() {
  detail.value = null
  if (logsTimer) { clearInterval(logsTimer); logsTimer = null }
}

function resetLogs() {
  logs.value = []
  fetchLogs().catch(() => {})
}

onUnmounted(() => {
  window.removeEventListener(AUTH_EVENT, updateAuthed)
  if (timer) clearInterval(timer)
  if (logsTimer) clearInterval(logsTimer)
})

watch([status, limit], () => refresh())

function doiHref(doi) {
  const v = String(doi || '').trim()
  if (!v) return '#'
  return v.startsWith('10.') ? `https://doi.org/${v}` : v
}

function pretty(obj) {
  try { return JSON.stringify(obj, null, 2) } catch { return String(obj) }
}

async function fetchLogs() {
  if (!detail.value || !detail.value.job_id || !isAdmin.value) return
  try {
    logsLoading.value = true
    logsError.value = ''
    const params = { limit: 100, order: 'desc' }
    const rows = await getJobLogs(detail.value.job_id, params)
    logs.value = Array.isArray(rows) ? rows : []
  } catch (e) {
    logsError.value = String(e)
  } finally {
    logsLoading.value = false
  }
}
</script>

<style scoped>
.jobs-view { max-width: 1100px; margin: 0 auto; }
.header-section { text-align: center; margin-bottom: 1.5rem; }
.section-title { display:flex; align-items:center; justify-content:center; gap:0.75rem; font-size:2rem; font-weight:600; color:#1a202c; margin:0 0 0.5rem 0; }
.section-title i { color:#0ea5e9; }
.section-description { color:#718096; margin:0; }
.admin-badge { margin-left: .5rem; font-size: .85rem; display:inline-flex; align-items:center; gap:.35rem; padding:.2rem .5rem; border-radius:999px; background:#ebf8ff; color:#2c5282; border:1px solid #90cdf4; }

.controls-row { display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom:1rem; flex-wrap:wrap; }
.filters { display:flex; align-items:center; gap:0.5rem; background:#f7fafc; padding:0.5rem 0.75rem; border:1px solid #e2e8f0; border-radius:10px; }
.filter-label { display:flex; align-items:center; gap:0.4rem; font-weight:600; color:#4a5568; }
.filter-select, .filter-input { padding:0.4rem 0.6rem; border:1px solid #cbd5e0; border-radius:8px; background:white; font-family:inherit; }
.refresh-button { display:flex; align-items:center; gap:0.5rem; padding:0.5rem 0.9rem; background:linear-gradient(135deg,#4299e1 0%, #2b6cb0 100%); color:white; border:none; border-radius:10px; font-weight:600; cursor:pointer; box-shadow:0 4px 12px rgba(66,153,225,0.3); }
.legend { display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap; }
.legend-item { display:inline-flex; align-items:center; gap:0.4rem; padding:0.3rem 0.6rem; border-radius:999px; font-size:0.85rem; border:1px solid transparent; }
.legend-item.running { background:#ebf8ff; border-color:#90cdf4; color:#2c5282; }
.legend-item.done { background:#f0fff4; border-color:#68d391; color:#22543d; }
.legend-item.error { background:#fed7d7; border-color:#fc8181; color:#c53030; }
.legend-item.pending { background:#fffaf0; border-color:#f6ad55; color:#c05621; }

.error-message { display:flex; align-items:center; gap:0.75rem; padding:0.9rem; background:linear-gradient(135deg,#fed7d7 0%, #feb2b2 100%); color:#c53030; border-radius:12px; border-left:4px solid #e53e3e; margin-bottom:1rem; font-weight:500; }

.jobs-card { background:white; border-radius:16px; border:1px solid #e2e8f0; box-shadow:0 10px 25px rgba(0,0,0,0.06); }
.jobs-header { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:1rem 1.25rem; border-bottom:1px solid #e2e8f0; }
.jobs-header h3 { display:flex; align-items:center; gap:0.5rem; font-size:1.1rem; margin:0; color:#2d3748; }
.auto-refresh { display:flex; align-items:center; gap:0.5rem; color:#4a5568; }
.auto-refresh .muted { font-size:0.85rem; opacity:0.8; }

.empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:2rem; color:#718096; }
.empty-state i { font-size:2rem; margin-bottom:0.5rem; color:#cbd5e0; }

.jobs-list { display:grid; gap:0.75rem; padding:1rem; max-height:600px; overflow-y:auto; }
.job-row { display:flex; gap:1rem; padding:1rem; border:1px solid #e2e8f0; border-radius:12px; align-items:stretch; }
.job-row.running { border-left:4px solid #63b3ed; }
.job-row.done { border-left:4px solid #68d391; }
.job-row.error { border-left:4px solid #fc8181; }
.job-row.pending { border-left:4px solid #f6ad55; }
.job-main { flex:1; display:grid; gap:0.5rem; }
.job-status { display:inline-flex; align-items:center; gap:0.5rem; font-weight:600; padding:0.35rem 0.6rem; border-radius:999px; border:1px solid transparent; width:fit-content; }
.job-status.running { background:#ebf8ff; border-color:#90cdf4; color:#2c5282; }
.job-status.done { background:#f0fff4; border-color:#68d391; color:#22543d; }
.job-status.error { background:#fed7d7; border-color:#fc8181; color:#c53030; }
.job-status.pending { background:#fffaf0; border-color:#f6ad55; color:#c05621; }
.job-meta { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:0.4rem 1rem; }
.meta-line { display:flex; gap:0.5rem; font-size:0.9rem; color:#4a5568; }
.meta-line .label { font-weight:600; color:#2d3748; }
.mono { font-family: 'Courier New', monospace; }
.progress { display:flex; align-items:center; gap:0.75rem; }
.bar { height:10px; background:#e2e8f0; border-radius:6px; flex:1; overflow:hidden; }
.fill { height:100%; background:linear-gradient(90deg,#805ad5 0%, #9f7aea 100%); transition:width .4s ease; }
.pct { font-weight:600; color:#2d3748; width:40px; text-align:right; }
.job-actions { display:flex; flex-direction:column; gap:0.5rem; width:140px; }
.action { display:flex; align-items:center; justify-content:center; gap:0.5rem; padding:0.5rem; border-radius:8px; border:1px solid #cbd5e0; background:#f7fafc; color:#2d3748; cursor:pointer; font-weight:600; }
.action.success { background:linear-gradient(135deg,#38a169 0%, #2f855a 100%); color:white; border:none; }
.action.danger { background:linear-gradient(135deg,#e53e3e 0%, #c53030 100%); color:white; border:none; }
.action:disabled { opacity:.6; cursor:not-allowed; }

.detail-modal { position:fixed; inset:0; background:rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; padding:1rem; z-index:50; }
.detail-card { background:white; width:min(1000px, 95vw); border-radius:16px; border:1px solid #e2e8f0; box-shadow:0 20px 40px rgba(0,0,0,0.2); max-height:90vh; display:flex; flex-direction:column; }
.detail-header { display:flex; justify-content:space-between; align-items:center; padding:1rem 1.25rem; border-bottom:1px solid #e2e8f0; }
.detail-header h3 { margin:0; display:flex; align-items:center; gap:0.5rem; }
.detail-header .close { border:none; background:transparent; font-size:1.1rem; cursor:pointer; }
.detail-body { padding:1rem 1.25rem; overflow:auto; }
.detail-meta { display:flex; flex-wrap:wrap; gap:1rem; margin-bottom:1rem; }
.error-block { display:flex; align-items:center; gap:0.5rem; padding:0.75rem; background:#fed7d7; color:#c53030; border-radius:8px; margin-bottom:1rem; border-left:4px solid #e53e3e; }
.results-list { display:grid; gap:0.75rem; }
.result { border:1px solid #e2e8f0; border-radius:10px; padding:0.75rem; background:#f7fafc; }
.result-head { display:flex; align-items:center; justify-content:space-between; gap:0.5rem; margin-bottom:0.5rem; }
.file { display:flex; align-items:center; gap:0.5rem; color:#2d3748; font-weight:600; }
.badge { display:inline-flex; align-items:center; gap:0.35rem; padding:0.25rem 0.5rem; border-radius:999px; font-size:0.8rem; font-weight:700; }
.badge.success { background:#c6f6d5; color:#22543d; }
.badge.error { background:#fed7d7; color:#c53030; }
.result-error { color:#c53030; background:#fed7d7; padding:0.5rem; border-radius:8px; border-left:4px solid #e53e3e; }
.result-fields { display:grid; gap:0.35rem; }
.field strong { color:#2d3748; margin-right:0.4rem; }
.links { margin-top:0.25rem; }
.links-list { display:flex; flex-direction:column; gap:0.25rem; margin-top:0.25rem; }
.resource-link { display:flex; align-items:center; gap:0.4rem; color:#3182ce; text-decoration:none; font-size:0.85rem; word-break:break-all; }
.raw-json { margin-top:1rem; border:1px solid #e2e8f0; border-radius:10px; overflow:hidden; }
.raw-json summary { display:flex; align-items:center; gap:0.5rem; padding:0.6rem 0.9rem; background:#f7fafc; cursor:pointer; font-weight:600; color:#4a5568; }
.raw-json pre { margin:0; padding:0.75rem; background:#2d3748; color:#e2e8f0; font-size:0.85rem; line-height:1.4; overflow:auto; }

@media (max-width: 768px) {
  .jobs-view { padding: 0 0.5rem; }
  .job-actions { width: 100px; }
}
</style>
