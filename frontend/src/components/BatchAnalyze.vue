<template>
  <div class="batch-analyze">
    <div class="header-section">
      <h2 class="section-title">
        <i class="fas fa-layer-group"></i>
        Analysis
      </h2>
      <p class="section-description">
        Upload one or more PDF files to analyze them and get comprehensive results.
      </p>
    </div>

    <div class="upload-section">
      <form @submit.prevent="startBatch" class="upload-form">
        <div class="file-input-wrapper">
          <input
            type="file"
            accept="application/pdf"
            multiple
            @change="onFiles"
            id="batch-files"
            class="file-input"
          />
          <label for="batch-files" class="file-input-label">
            <i class="fas fa-cloud-upload-alt"></i>
            <span v-if="!files.length">Choose PDF files or drag & drop</span>
            <span v-else class="files-selected">
              <i class="fas fa-file-pdf"></i>
              {{ files.length }} PDF file{{ files.length > 1 ? 's' : '' }} selected
            </span>
          </label>
        </div>

        <div v-if="files.length" class="file-list">
          <h4><i class="fas fa-list"></i> Selected Files</h4>
          <div class="files-grid">
            <div v-for="(file, idx) in files" :key="idx" class="file-item">
              <i class="fas fa-file-pdf"></i>
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ formatFileSize(file.size) }}</span>
            </div>
          </div>
        </div>

        <button
          type="submit"
          :disabled="!files.length || loading || !authed"
          class="analyze-button"
          :title="!authed ? 'Login in Settings to run analysis' : (files.length ? `Start analysis for ${files.length} file(s)` : 'Choose files to begin')"
        >
          <i v-if="loading" class="fas fa-spinner fa-spin"></i>
          <i v-else class="fas fa-play"></i>
          {{ loading ? 'Starting...' : (authed ? `Start Analysis (${files.length} files)` : 'Login to Start') }}
        </button>
      </form>
    </div>

    <div v-if="error" class="error-message">
      <i class="fas fa-exclamation-circle"></i>
      {{ error }}
    </div>

    <div v-if="job" class="job-status">
      <div class="job-header">
          <h3 class="job-title">
            <i class="fas fa-tasks"></i>
            Job Status
          </h3>
        <div class="job-id">
          <i class="fas fa-tag"></i>
          Job ID: {{ job.job_id }}
        </div>
      </div>

      <div class="progress-section">
        <div class="status-indicator" :class="job.status">
          <i :class="getStatusIcon(job.status)"></i>
          <span class="status-text">{{ getStatusText(job.status) }}</span>
        </div>

        <div class="progress-info">
          <span class="progress-text">
            {{ job.progress.current }} of {{ job.progress.total }} files processed
          </span>
          <span class="progress-percentage">{{ pct }}%</span>
        </div>

        <div class="progress-bar">
          <div class="progress-fill" :style="{width: pct + '%'}"></div>
        </div>

        <div class="view-jobs" v-if="job">
          <button class="view-jobs-button" @click="$emit('switch-tab', 'jobs')">
            <i class="fas fa-list-check"></i>
            View in Jobs
          </button>
        </div>
      </div>

      <div v-if="results && results.length" class="results-section">
        <div class="results-header">
          <h4><i class="fas fa-chart-line"></i> Results ({{ results.length }})</h4>
          <div v-if="job.status === 'done'" class="export-button">
            <button @click="onExportCsv" class="csv-link" :disabled="!authed" :title="!authed ? 'Login in Settings to download your CSV' : 'Download results as CSV'">
              <i class="fas fa-download"></i>
              {{ authed ? 'Download CSV' : 'Login to Download' }}
            </button>
          </div>
        </div>

        <div class="results-grid">
          <div v-for="(r, idx) in results" :key="idx" class="result-item">
            <div class="result-header">
              <div class="file-info">
                <i class="fas fa-file-pdf"></i>
                <span class="filename">{{ r.source_file || 'unknown.pdf' }}</span>
              </div>
              <div v-if="r.error" class="error-badge">
                <i class="fas fa-exclamation-circle"></i>
                Error
              </div>
              <div v-else class="success-badge">
                <i class="fas fa-check-circle"></i>
                Success
              </div>
            </div>

            <div v-if="r.error" class="error-details">
              {{ r.error }}
            </div>

            <div v-else class="result-content">
              <div v-if="r.title" class="result-field">
                <strong>Title:</strong> {{ r.title }}<span v-if="r.title_source"> (source: {{ r.title_source }})</span>
              </div>

              <div v-if="r.doi" class="result-field">
                <strong>DOI:</strong>
                <a :href="doiHref(r.doi)" target="_blank" rel="noopener" class="doi-link">
                  {{ r.doi }}
                  <i class="fas fa-external-link-alt"></i>
                </a>
              </div>

              <div v-if="r.data_availability_statement" class="result-field">
                <strong>Data Availability:</strong> {{ r.data_availability_statement }}
              </div>

              <div v-if="r.code_availability_statement" class="result-field">
                <strong>Code Availability:</strong> {{ r.code_availability_statement }}
              </div>

              <div v-if="r.data_sharing_license" class="result-field">
                <strong>Data License:</strong> {{ r.data_sharing_license }}
              </div>

              <div v-if="r.code_license" class="result-field">
                <strong>Code License:</strong> {{ r.code_license }}
              </div>

              <div v-if="r.data_links && r.data_links.length" class="result-field">
                <strong>Data Links ({{ r.data_links.length }}):</strong>
                <div class="links-list">
                  <a v-for="(l,i) in r.data_links" :key="'dl'+i" :href="l" target="_blank" rel="noopener" class="resource-link">
                    <i class="fas fa-external-link-alt"></i>{{ l }}
                  </a>
                </div>
              </div>

              <div v-if="r.code_links && r.code_links.length" class="result-field">
                <strong>Code Links ({{ r.code_links.length }}):</strong>
                <div class="links-list">
                  <a v-for="(l,i) in r.code_links" :key="'cl'+i" :href="l" target="_blank" rel="noopener" class="resource-link">
                    <i class="fas fa-external-link-alt"></i>{{ l }}
                  </a>
                </div>
              </div>

              <div v-if="r.confidence_scores && Object.keys(r.confidence_scores).length" class="confidence-mini">
                <strong>Confidence:</strong>
                <div class="confidence-badges">
                  <span v-for="(v,k) in r.confidence_scores" :key="k" class="confidence-badge">
                    {{ k }}: {{ (v*100).toFixed(0) }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { analyzeBatch, getJob, exportCsv, isAuthenticated, AUTH_EVENT } from '../api'

const files = ref([])
const job = ref(null)
const results = ref([])
const loading = ref(false)
const error = ref('')
let timer = null

function onFiles(e) {
  files.value = Array.from(e.target.files || [])
}

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function doiHref(doi) {
  const v = String(doi || '').trim()
  if (!v) return '#'
  return v.startsWith('10.') ? `https://doi.org/${v}` : v
}

function getStatusIcon(status) {
  switch (status) {
    case 'pending': return 'fas fa-clock'
    case 'running': return 'fas fa-spinner fa-spin'
    case 'done': return 'fas fa-check-circle'
    case 'error': return 'fas fa-exclamation-circle'
    default: return 'fas fa-question-circle'
  }
}

function getStatusText(status) {
  switch (status) {
    case 'pending': return 'Pending'
    case 'running': return 'Processing'
    case 'done': return 'Completed'
    case 'error': return 'Error'
    default: return 'Unknown'
  }
}

const pct = computed(() => {
  if (!job.value) return 0
  const { current, total } = job.value.progress || { current: 0, total: 1 }
  return total ? Math.round((current / total) * 100) : 0
})

const authed = ref(isAuthenticated())

async function onExportCsv() {
  if (!job.value) return
  try {
    await exportCsv(job.value.job_id)
  } catch (e) {
    error.value = String(e)
  }
}

async function poll(jobId) {
  try {
    const data = await getJob(jobId)
    job.value = data
    results.value = data.results || []
    if (data.status === 'done' || data.status === 'error') {
      clearInterval(timer)
      timer = null
    }
  } catch (e) {
    clearInterval(timer)
    timer = null
    error.value = String(e)
  }
}

async function startBatch() {
  if (!files.value.length) return
  loading.value = true
  error.value = ''
  job.value = null
  results.value = []
  try {
    const data = await analyzeBatch(files.value)
    job.value = data
    timer = setInterval(() => poll(data.job_id), 800)
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

function updateAuthed() { authed.value = isAuthenticated() }

onMounted(() => {
  window.addEventListener(AUTH_EVENT, updateAuthed)
  updateAuthed()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener(AUTH_EVENT, updateAuthed)
})
</script>

<style scoped>
.batch-analyze {
  max-width: 1000px;
  margin: 0 auto;
}

.header-section {
  text-align: center;
  margin-bottom: 2rem;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  font-size: 2rem;
  font-weight: 600;
  color: #1a202c;
  margin: 0 0 0.5rem 0;
}

.section-title i {
  color: #805ad5;
}

.section-description {
  color: #718096;
  font-size: 1.1rem;
  margin: 0;
  line-height: 1.5;
}

.upload-section {
  margin-bottom: 2rem;
}

.upload-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.file-input-wrapper {
  position: relative;
}

.file-input {
  position: absolute;
  opacity: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
}

.file-input-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  border: 3px dashed #cbd5e0;
  border-radius: 16px;
  background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  font-size: 1.1rem;
  color: #4a5568;
  font-weight: 500;
}

.file-input-label:hover {
  border-color: #805ad5;
  background: linear-gradient(135deg, #faf5ff 0%, #e9d8fd 100%);
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(128, 90, 213, 0.15);
}

.file-input-label i {
  font-size: 3rem;
  margin-bottom: 1rem;
  color: #805ad5;
}

.files-selected {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #22543d;
  font-weight: 600;
}

.files-selected i {
  font-size: 1.2rem !important;
  margin-bottom: 0 !important;
  color: #22543d !important;
}

.file-list {
  background: white;
  border-radius: 16px;
  padding: 1.5rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
}

.file-list h4 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 1rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: #2d3748;
}

.files-grid {
  display: grid;
  gap: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: #f7fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.file-item i {
  color: #e53e3e;
  font-size: 1.1rem;
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  font-weight: 500;
  color: #2d3748;
  font-size: 0.9rem;
  word-break: break-word;
}

.file-size {
  color: #718096;
  font-size: 0.8rem;
  flex-shrink: 0;
}

.analyze-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1rem 2rem;
  background: linear-gradient(135deg, #805ad5 0%, #6b46c1 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 15px rgba(128, 90, 213, 0.3);
  font-family: inherit;
}

.analyze-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(128, 90, 213, 0.4);
}

.analyze-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: 0 4px 15px rgba(128, 90, 213, 0.2);
}

.error-message {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
  color: #c53030;
  border-radius: 12px;
  border-left: 4px solid #e53e3e;
  margin-bottom: 2rem;
  font-weight: 500;
}

.job-status {
  background: white;
  border-radius: 20px;
  padding: 2rem;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  border: 1px solid #e2e8f0;
  animation: slideUp 0.5s ease-out;
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.job-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.5rem;
  font-weight: 600;
  color: #2d3748;
  margin: 0;
}

.job-title i {
  color: #805ad5;
}

.job-id {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: #f7fafc;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.85rem;
  color: #4a5568;
  font-weight: 500;
  border: 1px solid #e2e8f0;
}

.progress-section {
  margin-bottom: 2rem;
}

.view-jobs {
  margin-top: 1rem;
}

.view-jobs-button {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.9rem;
  background: linear-gradient(135deg,#4299e1 0%, #2b6cb0 100%);
  color: white;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(66,153,225,0.3);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding: 1rem;
  border-radius: 12px;
  font-weight: 600;
  font-size: 1.1rem;
  border: 2px solid transparent;
}

.status-indicator.pending {
  background: linear-gradient(135deg, #fef5e7 0%, #fed7aa 100%);
  color: #c05621;
  border-color: #f6ad55;
}

.status-indicator.running {
  background: linear-gradient(135deg, #ebf8ff 0%, #bee3f8 100%);
  color: #2c5aa0;
  border-color: #63b3ed;
}

.status-indicator.done {
  background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
  color: #22543d;
  border-color: #68d391;
}

.status-indicator.error {
  background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
  color: #c53030;
  border-color: #fc8181;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  font-weight: 500;
  color: #4a5568;
}

.progress-percentage {
  font-size: 1.1rem;
  font-weight: 600;
  color: #2d3748;
}

.progress-bar {
  height: 12px;
  background: #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #805ad5 0%, #9f7aea 100%);
  border-radius: 6px;
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 4px rgba(128, 90, 213, 0.3);
}

.results-section {
  margin-top: 2rem;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.results-header h4 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.2rem;
  font-weight: 600;
  color: #2d3748;
  margin: 0;
}

.csv-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  background: linear-gradient(135deg, #38a169 0%, #2f855a 100%);
  color: white;
  text-decoration: none;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(56, 161, 105, 0.3);
}

.csv-link:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(56, 161, 105, 0.4);
}

.results-grid {
  display: grid;
  gap: 1rem;
  max-height: 600px;
  overflow-y: auto;
}

.result-item {
  background: #f7fafc;
  border-radius: 12px;
  padding: 1.5rem;
  border: 1px solid #e2e8f0;
  transition: all 0.3s ease;
}

.result-item:hover {
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.file-info i {
  color: #e53e3e;
  font-size: 1.1rem;
}

.filename {
  font-weight: 600;
  color: #2d3748;
  font-size: 0.95rem;
  word-break: break-word;
}

.error-badge,
.success-badge {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.8rem;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
}

.error-badge {
  background: #fed7d7;
  color: #c53030;
}

.success-badge {
  background: #c6f6d5;
  color: #22543d;
}

.error-details {
  color: #c53030;
  background: #fed7d7;
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.9rem;
  border-left: 4px solid #e53e3e;
}

.result-content {
  display: grid;
  gap: 0.75rem;
}

.result-field {
  font-size: 0.9rem;
  line-height: 1.4;
}

.result-field strong {
  color: #2d3748;
  display: block;
  margin-bottom: 0.25rem;
}

.doi-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: #3182ce;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
}

.doi-link:hover {
  color: #2c5aa0;
}

.links-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.5rem;
}

.resource-link {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #3182ce;
  text-decoration: none;
  font-size: 0.8rem;
  padding: 0.4rem 0;
  transition: all 0.2s ease;
  word-break: break-all;
}

.resource-link:hover {
  color: #2c5aa0;
  transform: translateX(4px);
}

.resource-link i {
  font-size: 0.7rem;
  opacity: 0.7;
  flex-shrink: 0;
}

.confidence-mini {
  margin-top: 0.5rem;
}

.confidence-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.confidence-badge {
  background: #e2e8f0;
  color: #4a5568;
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .batch-analyze {
    padding: 0 1rem;
  }

  .section-title {
    font-size: 1.5rem;
    flex-direction: column;
    gap: 0.5rem;
  }

  .file-input-label {
    padding: 2rem 1rem;
  }

  .job-status {
    padding: 1.5rem;
  }

  .job-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .results-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .result-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .files-grid {
    max-height: 200px;
  }

  .results-grid {
    max-height: 400px;
  }
}
</style>
