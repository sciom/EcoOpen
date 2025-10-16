<template>
  <div class="settings-view">
    <div class="header-section">
      <h2 class="section-title">
        <i class="fas fa-cog"></i>
        Settings & Configuration
      </h2>
      <p class="section-description">
        Configure API connections and monitor system status.
      </p>
    </div>

    <div class="settings-grid">
      <!-- API Configuration Card -->
      <div class="settings-card">
        <div class="card-header">
          <h3>
            <i class="fas fa-server"></i>
            API Configuration
          </h3>
          <p>Configure the backend API endpoint</p>
        </div>

        <div class="form-section">
          <label class="form-label">
            <i class="fas fa-link"></i>
            API Base URL
          </label>
          <input
            v-model="apiBase"
            placeholder="http://localhost:8000"
            class="form-input"
            type="url"
          />
          <p class="form-help">
            Override is stored in localStorage. Leave empty to use default.
          </p>

          <div class="button-group">
            <button @click="saveBase" class="save-button">
              <i class="fas fa-save"></i>
              Save Configuration
            </button>
            <button @click="resetBase" class="reset-button">
              <i class="fas fa-undo"></i>
              Reset to Default
            </button>
          </div>
        </div>
      </div>

      <!-- Live Status Card -->
      <div class="settings-card">
        <div class="card-header">
          <h3>
            <i class="fas fa-heartbeat"></i>
            Live System Status
          </h3>
          <p>Real-time health monitoring</p>
        </div>

        <div class="status-section">
          <button @click="refresh" :disabled="loading" class="refresh-button">
            <i :class="loading ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i>
            {{ loading ? 'Refreshing...' : 'Refresh Status' }}
          </button>

          <div v-if="error" class="error-alert">
            <i class="fas fa-exclamation-triangle"></i>
            <div>
              <strong>Connection Error</strong>
              <p>{{ error }}</p>
            </div>
          </div>

          <div v-if="health" class="health-summary">
            <div class="health-item" :class="getHealthClass(health.status)">
              <div class="health-icon">
                <i :class="getStatusIcon(health.status)"></i>
              </div>
              <div class="health-info">
                <strong>Overall Status</strong>
                <span>{{ getStatusText(health.status) }}</span>
              </div>
            </div>

            <div class="services-grid">
              <div class="service-item" :class="health.agent_reachable ? 'online' : 'offline'">
                <i class="fas fa-robot"></i>
                <div class="service-info">
                  <span class="service-name">AI Agent</span>
                  <span class="service-status">{{ health.agent_reachable ? 'Online' : 'Offline' }}</span>
                  <div v-if="health.agent_model" class="service-model">{{ health.agent_model }}</div>
                </div>
                <div class="service-indicator" :class="health.agent_reachable ? 'active' : 'inactive'"></div>
              </div>

              <div class="service-item" :class="health.embeddings_reachable ? 'online' : 'offline'">
                <i class="fas fa-vector-square"></i>
                <div class="service-info">
                  <span class="service-name">Embeddings</span>
                  <span class="service-status">{{ health.embeddings_reachable ? 'Online' : 'Offline' }}</span>
                </div>
                <div class="service-indicator" :class="health.embeddings_reachable ? 'active' : 'inactive'"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Authentication Card -->
      <div class="settings-card">
        <div class="card-header">
          <h3>
            <i class="fas fa-user-lock"></i>
            Authentication
          </h3>
          <p>Login is required to use the app (analyze, batch, export).</p>
        </div>

        <div class="form-section">
          <div class="auth-row">
            <div class="auth-status" :class="authed ? 'authed' : 'anon'">
              <i :class="authed ? 'fas fa-user-check' : 'fas fa-user'" />
              <span v-if="authed">{{ email }}</span>
              <span v-else>Not signed in</span>
            </div>
            <button v-if="authed" @click="onLogout" class="reset-button">
              <i class="fas fa-sign-out-alt"></i>
              Logout
            </button>
          </div>

          <div v-if="!authed" class="auth-grid">
            <input v-model="email" type="email" placeholder="email@example.com" class="form-input" />
            <input v-model="password" type="password" placeholder="Password" class="form-input" />

            <div class="button-group">
              <button @click="onLogin" class="save-button" :disabled="authLoading">
                <i :class="authLoading ? 'fas fa-spinner fa-spin' : 'fas fa-sign-in-alt'" />
                {{ authLoading ? 'Signing in...' : 'Login' }}
              </button>
              <button @click="onRegister" class="reset-button" :disabled="authLoading">
                <i class="fas fa-user-plus"></i>
                Register
              </button>
            </div>

            <div v-if="authError" class="error-alert">
              <i class="fas fa-exclamation-triangle"></i>
              <div>
                <strong>Authentication Error</strong>
                <p>{{ authError }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Server Configuration Card -->
    <div v-if="config" class="full-width-card">
      <div class="card-header">
        <h3>
          <i class="fas fa-cogs"></i>
          Server Configuration
        </h3>
        <button @click="showFullConfig = !showFullConfig" class="toggle-button">
          <i :class="showFullConfig ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
          {{ showFullConfig ? 'Hide Details' : 'Show Details' }}
        </button>
      </div>

      <transition name="config-slide">
        <div v-if="showFullConfig" class="config-content">
          <div class="config-wrapper">
            <pre class="config-json">{{ config }}</pre>
          </div>
        </div>
      </transition>
    </div>

    <!-- Quick Actions Card -->
    <div class="full-width-card">
      <div class="card-header">
        <h3>
          <i class="fas fa-bolt"></i>
          Quick Actions
        </h3>
        <p>Common tasks and shortcuts</p>
      </div>

      <div class="actions-grid">
        <button @click="testConnection" :disabled="loading" class="action-button">
          <i class="fas fa-wifi"></i>
          <span>Test Connection</span>
        </button>

        <button @click="refresh" :disabled="loading" class="action-button">
          <i class="fas fa-sync-alt"></i>
          <span>Refresh All</span>
        </button>

        <button @click="clearStorage" class="action-button warning">
          <i class="fas fa-trash-alt"></i>
          <span>Clear Storage</span>
        </button>

        <button @click="exportSettings" class="action-button">
          <i class="fas fa-download"></i>
          <span>Export Settings</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { getHealth, getConfig, getApiBase, setApiBase, login, register, logout, isAuthenticated, getAuthEmail, AUTH_EVENT } from '../api'

const apiBase = ref(getApiBase())
const loading = ref(false)
const error = ref('')
const health = ref(null)
const config = ref('')
const showFullConfig = ref(false)

// Auth state
const authed = ref(isAuthenticated())
const email = ref(getAuthEmail())
const password = ref('')
const authLoading = ref(false)
const authError = ref('')

function saveBase() {
  setApiBase(apiBase.value)
  // Show a brief success indication
  const originalValue = apiBase.value
  apiBase.value = '✓ Saved'
  setTimeout(() => { apiBase.value = originalValue }, 1000)
}

function resetBase() {
  apiBase.value = ''
  setApiBase('')
}

function getStatusIcon(status) {
  const s = status === 'degraded' ? 'warning' : status
  switch (s) {
    case 'ok': return 'fas fa-check-circle'
    case 'error': return 'fas fa-exclamation-circle'
    case 'warning': return 'fas fa-exclamation-triangle'
    default: return 'fas fa-question-circle'
  }
}

function getStatusText(status) {
  const s = status === 'degraded' ? 'warning' : status
  switch (s) {
    case 'ok': return 'All Systems Operational'
    case 'error': return 'System Error Detected'
    case 'warning': return 'System Warning'
    default: return 'Status Unknown'
  }
}

function getHealthClass(status) {
  const s = status === 'degraded' ? 'warning' : status
  switch (s) {
    case 'ok': return 'healthy'
    case 'error': return 'error'
    case 'warning': return 'warning'
    default: return 'unknown'
  }
}

async function testConnection() {
  try {
    loading.value = true
    error.value = ''
    await getHealth()
    // Show success message briefly
    error.value = ''
    const temp = document.createElement('div')
    temp.textContent = '✓ Connection successful!'
    temp.style.color = '#38a169'
    temp.style.fontWeight = 'bold'
    // This is a simple way to show success - in a real app you might use a toast
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

async function refresh() {
  try {
    loading.value = true
    error.value = ''
    const [h, c] = await Promise.all([getHealth(), getConfig()])
    health.value = h
    config.value = JSON.stringify(c, null, 2)
  } catch (e) {
    error.value = String(e)
    health.value = null
    config.value = ''
  } finally {
    loading.value = false
  }
}

function clearStorage() {
  if (confirm('Are you sure you want to clear all stored settings? This action cannot be undone.')) {
    localStorage.clear()
    apiBase.value = getApiBase()
  }
}

function exportSettings() {
  const settings = {
    apiBase: getApiBase(),
    timestamp: new Date().toISOString(),
    version: '1.0'
  }

  const blob = new Blob([JSON.stringify(settings, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'ecoopen-llm-settings.json'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function onLogin() {
  try {
    authLoading.value = true
    authError.value = ''
    await login(email.value, password.value)
  } catch (e) {
    authError.value = String(e)
  } finally {
    authLoading.value = false
  }
}

async function onRegister() {
  try {
    authLoading.value = true
    authError.value = ''
    await register(email.value, password.value)
  } catch (e) {
    authError.value = String(e)
  } finally {
    authLoading.value = false
  }
}

function onLogout() {
  logout()
}

function updateAuth() {
  authed.value = isAuthenticated()
  email.value = getAuthEmail()
  password.value = ''
}

onMounted(() => {
  refresh()
  window.addEventListener(AUTH_EVENT, updateAuth)
  updateAuth()
})

onBeforeUnmount(() => {
  window.removeEventListener(AUTH_EVENT, updateAuth)
})
</script>

<style scoped>
.settings-view {
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

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
}

.settings-card,
.full-width-card {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.settings-card:hover,
.full-width-card:hover {
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.full-width-card {
  margin-bottom: 2rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.card-header h3 {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.3rem;
  font-weight: 600;
  color: #2d3748;
  margin: 0 0 0.25rem 0;
}

.card-header h3 i {
  color: #805ad5;
  font-size: 1.1rem;
}

.card-header p {
  margin: 0;
  color: #718096;
  font-size: 0.95rem;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: #2d3748;
  font-size: 0.95rem;
}

.form-label i {
  color: #805ad5;
  font-size: 0.9rem;
}

.form-input {
  padding: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  font-size: 1rem;
  transition: all 0.3s ease;
  font-family: inherit;
  background: #f7fafc;
}

.form-input:focus {
  outline: none;
  border-color: #805ad5;
  background: white;
  box-shadow: 0 0 0 3px rgba(128, 90, 213, 0.1);
}

.auth-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.auth-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
}

.auth-status.authed {
  color: #22543d;
}

.auth-status.anon {
  color: #4a5568;
}

.auth-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 600px) {
  .auth-grid {
    grid-template-columns: 1fr;
  }
}

.form-help {
  font-size: 0.85rem;
  color: #718096;
  margin: 0;
  line-height: 1.4;
}

.button-group {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.save-button,
.reset-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.3s ease;
  border: none;
  font-family: inherit;
}

.save-button {
  background: linear-gradient(135deg, #38a169 0%, #2f855a 100%);
  color: white;
  box-shadow: 0 4px 15px rgba(56, 161, 105, 0.3);
}

.save-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(56, 161, 105, 0.4);
}

.reset-button {
  background: #f7fafc;
  color: #4a5568;
  border: 1px solid #e2e8f0;
}

.reset-button:hover {
  background: #edf2f7;
  border-color: #cbd5e0;
}

.status-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.refresh-button {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  background: linear-gradient(135deg, #4299e1 0%, #2b6cb0 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(66, 153, 225, 0.3);
  font-family: inherit;
  align-self: flex-start;
}

.refresh-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(66, 153, 225, 0.4);
}

.refresh-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.error-alert {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
  background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
  color: #c53030;
  border-radius: 12px;
  border-left: 4px solid #e53e3e;
}

.error-alert i {
  font-size: 1.2rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
}

.error-alert strong {
  display: block;
  margin-bottom: 0.25rem;
}

.error-alert p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.3;
}

.health-summary {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border-radius: 12px;
  border: 2px solid transparent;
}

.health-item.healthy {
  background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
  border-color: #68d391;
}

.health-item.error {
  background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
  border-color: #fc8181;
}

.health-item.warning {
  background: linear-gradient(135deg, #fef5e7 0%, #fed7aa 100%);
  border-color: #f6ad55;
}

.health-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  font-size: 1.2rem;
  flex-shrink: 0;
}

.health-item.healthy .health-icon {
  color: #22543d;
}

.health-item.error .health-icon {
  color: #c53030;
}

.health-item.warning .health-icon {
  color: #c05621;
}

.health-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.health-info strong {
  font-size: 1rem;
  color: #2d3748;
}

.health-info span {
  font-size: 0.9rem;
  opacity: 0.8;
}

.services-grid {
  display: grid;
  gap: 0.75rem;
}

.service-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.service-item.online {
  background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
  border: 1px solid #68d391;
}

.service-item.offline {
  background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
  border: 1px solid #fc8181;
}

.service-item i {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.service-item.online i {
  color: #22543d;
}

.service-item.offline i {
  color: #c53030;
}

.service-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.service-name {
  font-weight: 600;
  color: #2d3748;
  font-size: 0.95rem;
}

.service-status {
  font-size: 0.8rem;
  opacity: 0.8;
}

.service-model {
  font-size: 0.75rem;
  background: rgba(255, 255, 255, 0.4);
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  display: inline-block;
  margin-top: 0.25rem;
  border: 1px solid rgba(255, 255, 255, 0.6);
}

.service-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.service-indicator.active {
  background: #38a169;
  box-shadow: 0 0 8px rgba(56, 161, 105, 0.6);
}

.service-indicator.inactive {
  background: #e53e3e;
  box-shadow: 0 0 8px rgba(229, 62, 62, 0.6);
}

.toggle-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #f7fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #4a5568;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  font-size: 0.9rem;
  font-weight: 500;
}

.toggle-button:hover {
  background: #edf2f7;
  border-color: #cbd5e0;
}

.config-slide-enter-active,
.config-slide-leave-active {
  transition: all 0.3s ease;
}

.config-slide-enter-from,
.config-slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding: 0;
}

.config-slide-enter-to,
.config-slide-leave-from {
  opacity: 1;
  max-height: 500px;
  padding: 1rem 0;
}

.config-content {
  border-top: 1px solid #e2e8f0;
  padding: 1rem 0;
}

.config-wrapper {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

.config-json {
  padding: 1.5rem;
  background: #2d3748;
  color: #e2e8f0;
  font-size: 0.85rem;
  line-height: 1.4;
  overflow-x: auto;
  margin: 0;
  font-family: 'Courier New', monospace;
  white-space: pre-wrap;
  max-height: 400px;
  overflow-y: auto;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.action-button {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1.5rem 1rem;
  background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
  font-weight: 600;
  color: #4a5568;
}

.action-button:hover:not(:disabled) {
  border-color: #cbd5e0;
  background: linear-gradient(135deg, #edf2f7 0%, #e2e8f0 100%);
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.action-button.warning {
  border-color: #fed7aa;
  color: #c05621;
}

.action-button.warning:hover:not(:disabled) {
  border-color: #f6ad55;
  background: linear-gradient(135deg, #fef5e7 0%, #fed7aa 100%);
}

.action-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-button i {
  font-size: 1.5rem;
}

.action-button span {
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .settings-view {
    padding: 0 1rem;
  }

  .section-title {
    font-size: 1.5rem;
    flex-direction: column;
    gap: 0.5rem;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .button-group {
    flex-direction: column;
  }

  .service-item {
    flex-direction: column;
    text-align: center;
    gap: 0.75rem;
  }

  .actions-grid {
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  }

  .action-button {
    padding: 1rem 0.5rem;
  }
}
</style>
