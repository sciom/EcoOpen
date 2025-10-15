<template>
  <div class="single-analyze">
    <div class="header-section">
      <h2 class="section-title">
        <i class="fas fa-file-pdf"></i>
        Analyze Single PDF
      </h2>
      <p class="section-description">
        Upload a scientific PDF to extract data and code availability information using AI analysis.
      </p>
    </div>

    <div class="upload-section">
      <form @submit.prevent="onSubmit" class="upload-form">
        <div class="file-input-wrapper">
          <input 
            type="file" 
            accept="application/pdf" 
            @change="onFile" 
            id="pdf-file"
            class="file-input"
          />
          <label for="pdf-file" class="file-input-label">
            <i class="fas fa-cloud-upload-alt"></i>
            <span v-if="!file">Choose PDF file or drag & drop</span>
            <span v-else class="file-selected">
              <i class="fas fa-file-pdf"></i>
              {{ file.name }}
            </span>
          </label>
        </div>
        <button 
          type="submit" 
          :disabled="!file || loading || !authed" 
          class="analyze-button"
          :title="!authed ? 'Login in Settings to analyze a PDF' : (file ? 'Analyze selected PDF' : 'Choose a file to begin')"
        >
          <i v-if="loading" class="fas fa-spinner fa-spin"></i>
          <i v-else class="fas fa-search"></i>
          {{ loading ? 'Analyzing...' : (authed ? 'Analyze PDF' : 'Login to Analyze') }}
        </button>
      </form>
    </div>

    <div v-if="error" class="error-message">
      <i class="fas fa-exclamation-circle"></i>
      {{ error }}
    </div>

    <div v-if="result" class="results-section">
      <h3 class="results-title">
        <i class="fas fa-check-circle"></i>
        Analysis Results
      </h3>
      
      <div class="result-card">
        <div class="result-header">
          <div class="file-info">
            <i class="fas fa-file-pdf"></i>
            <span class="filename">{{ result.source_file || 'unknown.pdf' }}</span>
          </div>
        </div>

        <div v-if="result.title" class="result-item">
          <h4><i class="fas fa-heading"></i> Title</h4>
          <p class="paper-title">{{ result.title }}</p>
        </div>

        <div v-if="result.doi" class="result-item">
          <h4><i class="fas fa-link"></i> DOI</h4>
          <a :href="doiHref(result.doi)" target="_blank" rel="noopener" class="doi-link">
            {{ result.doi }}
            <i class="fas fa-external-link-alt"></i>
          </a>
        </div>

        <div v-if="result.data_availability_statement" class="result-item">
          <h4><i class="fas fa-database"></i> Data Availability</h4>
          <p class="statement">{{ result.data_availability_statement }}</p>
        </div>

        <div v-if="result.code_availability_statement" class="result-item">
          <h4><i class="fas fa-code"></i> Code Availability</h4>
          <p class="statement">{{ result.code_availability_statement }}</p>
        </div>

        <div v-if="result.data_sharing_license" class="result-item">
          <h4><i class="fas fa-balance-scale"></i> Data Sharing License</h4>
          <p class="license">{{ result.data_sharing_license }}</p>
        </div>

        <div v-if="result.code_license" class="result-item">
          <h4><i class="fas fa-file-contract"></i> Code License</h4>
          <p class="license">{{ result.code_license }}</p>
        </div>

        <div v-if="(result.data_links && result.data_links.length) || (result.code_links && result.code_links.length)" class="links-section">
          <div v-if="result.data_links && result.data_links.length" class="links-group">
            <h4><i class="fas fa-database"></i> Data Links ({{ result.data_links.length }})</h4>
            <div class="links-list">
              <a v-for="(l, i) in result.data_links" :key="'dl'+i" :href="l" target="_blank" rel="noopener" class="resource-link">
                <i class="fas fa-external-link-alt"></i>
                {{ l }}
              </a>
            </div>
          </div>
          
          <div v-if="result.code_links && result.code_links.length" class="links-group">
            <h4><i class="fas fa-code"></i> Code Links ({{ result.code_links.length }})</h4>
            <div class="links-list">
              <a v-for="(l, i) in result.code_links" :key="'cl'+i" :href="l" target="_blank" rel="noopener" class="resource-link">
                <i class="fas fa-external-link-alt"></i>
                {{ l }}
              </a>
            </div>
          </div>
        </div>

        <div v-if="result.confidence_scores && Object.keys(result.confidence_scores).length" class="confidence-section">
          <h4><i class="fas fa-chart-bar"></i> Confidence Scores</h4>
          <div class="confidence-grid">
            <div v-for="(v,k) in result.confidence_scores" :key="k" class="confidence-item">
              <span class="confidence-label">{{ k }}</span>
              <div class="confidence-bar">
                <div class="confidence-fill" :style="{width: (v*100) + '%'}"></div>
              </div>
              <span class="confidence-value">{{ (v*100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>

        <div v-if="result.error" class="result-error">
          <i class="fas fa-exclamation-triangle"></i>
          Error: {{ result.error }}
        </div>

        <details class="raw-json">
          <summary>
            <i class="fas fa-code"></i>
            Raw JSON Response
          </summary>
          <pre class="json-content">{{ pretty(result) }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { analyzeSingle, isAuthenticated, AUTH_EVENT } from '../api'

const file = ref(null)
const loading = ref(false)
const error = ref('')
const result = ref(null)
const authed = ref(isAuthenticated())

function updateAuthed() { authed.value = isAuthenticated() }

onMounted(() => {
  window.addEventListener(AUTH_EVENT, updateAuthed)
  updateAuthed()
})

onUnmounted(() => {
  window.removeEventListener(AUTH_EVENT, updateAuthed)
})

function onFile(e) {
  file.value = e.target.files?.[0] || null
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2)
}

function doiHref(doi) {
  const v = String(doi || '').trim()
  if (!v) return '#'
  return v.startsWith('10.') ? `https://doi.org/${v}` : v
}

async function onSubmit() {
  if (!file.value) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await analyzeSingle(file.value)
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.single-analyze {
  max-width: 800px;
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
  color: #3182ce;
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
  border-color: #3182ce;
  background: linear-gradient(135deg, #ebf8ff 0%, #bee3f8 100%);
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(49, 130, 206, 0.15);
}

.file-input-label i {
  font-size: 3rem;
  margin-bottom: 1rem;
  color: #3182ce;
}

.file-selected {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #22543d;
  font-weight: 600;
}

.file-selected i {
  font-size: 1.2rem !important;
  margin-bottom: 0 !important;
  color: #22543d !important;
}

.analyze-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1rem 2rem;
  background: linear-gradient(135deg, #3182ce 0%, #2c5aa0 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 15px rgba(49, 130, 206, 0.3);
  font-family: inherit;
}

.analyze-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(49, 130, 206, 0.4);
}

.analyze-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: 0 4px 15px rgba(49, 130, 206, 0.2);
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

.results-section {
  animation: slideUp 0.5s ease-out;
}

.results-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.5rem;
  font-weight: 600;
  color: #22543d;
  margin: 0 0 1.5rem 0;
}

.results-title i {
  color: #38a169;
}

.result-card {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
  border: 1px solid #e2e8f0;
}

.result-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e2e8f0;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.file-info i {
  color: #e53e3e;
  font-size: 1.2rem;
}

.filename {
  font-weight: 600;
  color: #2d3748;
  font-size: 1.1rem;
}

.result-item {
  margin-bottom: 1.5rem;
}

.result-item h4 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 600;
  color: #2d3748;
  margin: 0 0 0.5rem 0;
}

.result-item h4 i {
  color: #3182ce;
  width: 20px;
}

.paper-title {
  font-size: 1.1rem;
  font-weight: 500;
  color: #1a202c;
  line-height: 1.4;
  margin: 0;
}

.doi-link {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: #3182ce;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
}

.doi-link:hover {
  color: #2c5aa0;
}

.statement {
  background: #f7fafc;
  padding: 1rem;
  border-radius: 8px;
  border-left: 4px solid #3182ce;
  margin: 0;
  line-height: 1.5;
  white-space: pre-wrap;
}

.license {
  background: #fffaf0;
  padding: 1rem;
  border-radius: 8px;
  border-left: 4px solid #dd6b20;
  margin: 0;
  line-height: 1.5;
  color: #744210;
  font-style: italic;
}

.links-section {
  display: grid;
  gap: 1.5rem;
  margin: 1.5rem 0;
}

.links-group h4 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 600;
  color: #2d3748;
  margin: 0 0 0.75rem 0;
}

.links-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.resource-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #f7fafc;
  border-radius: 8px;
  color: #3182ce;
  text-decoration: none;
  font-size: 0.9rem;
  transition: all 0.2s ease;
  border: 1px solid #e2e8f0;
}

.resource-link:hover {
  background: #edf2f7;
  transform: translateX(4px);
}

.resource-link i {
  font-size: 0.8rem;
  opacity: 0.7;
}

.confidence-section {
  margin: 1.5rem 0;
}

.confidence-grid {
  display: grid;
  gap: 1rem;
}

.confidence-item {
  display: grid;
  grid-template-columns: 1fr 2fr auto;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  background: #f7fafc;
  border-radius: 8px;
}

.confidence-label {
  font-weight: 500;
  color: #4a5568;
  text-transform: capitalize;
}

.confidence-bar {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  background: linear-gradient(90deg, #38a169 0%, #48bb78 100%);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.confidence-value {
  font-weight: 600;
  color: #2d3748;
  font-size: 0.9rem;
}

.result-error {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: #fed7d7;
  color: #c53030;
  border-radius: 8px;
  font-weight: 500;
  margin: 1rem 0;
}

.raw-json {
  margin-top: 1.5rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.raw-json summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background: #f7fafc;
  cursor: pointer;
  font-weight: 500;
  color: #4a5568;
  transition: background 0.2s ease;
}

.raw-json summary:hover {
  background: #edf2f7;
}

.json-content {
  padding: 1rem;
  background: #2d3748;
  color: #e2e8f0;
  font-size: 0.85rem;
  line-height: 1.4;
  overflow-x: auto;
  margin: 0;
  font-family: 'Courier New', monospace;
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
  .single-analyze {
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
  
  .result-card {
    padding: 1.5rem;
  }
  
  .confidence-item {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
  
  .links-section {
    grid-template-columns: 1fr;
  }
}
</style>
