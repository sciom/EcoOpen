<template>
  <div class="health-status">
    <div class="header-section">
      <h2 class="section-title">
        <i class="fas fa-heartbeat"></i>
        System Health
      </h2>
      <p class="section-description">
        Monitor the health and status of all system components and services.
      </p>
    </div>

    <div class="actions-section">
      <button @click="refresh" :disabled="loading" class="refresh-button">
        <i :class="loading ? 'fas fa-spinner fa-spin' : 'fas fa-sync-alt'"></i>
        {{ loading ? 'Checking...' : 'Refresh Status' }}
      </button>
    </div>

    <div v-if="error" class="error-message">
      <i class="fas fa-exclamation-circle"></i>
      <div>
        <strong>Connection Error</strong>
        <p>{{ error }}</p>
      </div>
    </div>

    <div v-if="health" class="health-overview">
      <div class="status-card" :class="statusClass(health.status)">
        <div class="status-icon">
          <i :class="getStatusIcon(health.status)"></i>
        </div>
        <div class="status-info">
          <h3>System Status</h3>
          <p class="status-text">{{ getStatusText(health.status) }}</p>
        </div>
      </div>

      <div class="components-grid">
        <div class="component-card" :class="health.agent_reachable ? 'healthy' : 'unhealthy'">
          <div class="component-icon">
            <i class="fas fa-robot"></i>
          </div>
          <div class="component-info">
            <h4>AI Agent</h4>
            <p>{{ health.agent_reachable ? 'Connected' : 'Disconnected' }}</p>
            <div v-if="health.agent_model" class="model-info">
              <i class="fas fa-brain"></i>
              {{ health.agent_model }}
            </div>
          </div>
          <div class="status-indicator" :class="health.agent_reachable ? 'online' : 'offline'">
            <i :class="health.agent_reachable ? 'fas fa-check-circle' : 'fas fa-times-circle'"></i>
          </div>
        </div>

        <div class="component-card" :class="health.embeddings_reachable ? 'healthy' : 'unhealthy'">
          <div class="component-icon">
            <i class="fas fa-vector-square"></i>
          </div>
          <div class="component-info">
            <h4>Embeddings Service</h4>
            <p>{{ health.embeddings_reachable ? 'Connected' : 'Disconnected' }}</p>
          </div>
          <div class="status-indicator" :class="health.embeddings_reachable ? 'online' : 'offline'">
            <i :class="health.embeddings_reachable ? 'fas fa-check-circle' : 'fas fa-times-circle'"></i>
          </div>
        </div>
      </div>
    </div>

    <div v-if="config" class="config-section">
      <div class="config-header">
        <h3>
          <i class="fas fa-cogs"></i>
          Server Configuration
        </h3>
        <button @click="showConfig = !showConfig" class="toggle-button">
          <i :class="showConfig ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
          {{ showConfig ? 'Hide' : 'Show' }}
        </button>
      </div>
      
      <div v-if="showConfig" class="config-content">
        <pre class="config-json">{{ config }}</pre>
      </div>
    </div>

    <div class="diagnostics-section">
      <h3>
        <i class="fas fa-stethoscope"></i>
        Quick Diagnostics
      </h3>
      <div class="diagnostics-grid">
        <div class="diagnostic-item" :class="health?.status === 'ok' ? 'pass' : 'fail'">
          <i :class="health?.status === 'ok' ? 'fas fa-check' : 'fas fa-times'"></i>
          <span>Overall Health</span>
        </div>
        <div class="diagnostic-item" :class="health?.agent_reachable ? 'pass' : 'fail'">
          <i :class="health?.agent_reachable ? 'fas fa-check' : 'fas fa-times'"></i>
          <span>AI Processing</span>
        </div>
        <div class="diagnostic-item" :class="health?.embeddings_reachable ? 'pass' : 'fail'">
          <i :class="health?.embeddings_reachable ? 'fas fa-check' : 'fas fa-times'"></i>
          <span>Vector Processing</span>
        </div>
        <div class="diagnostic-item" :class="config ? 'pass' : 'fail'">
          <i :class="config ? 'fas fa-check' : 'fas fa-times'"></i>
          <span>Configuration</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getHealth, getConfig } from '../api'

const health = ref(null)
const config = ref(null)
const loading = ref(false)
const error = ref('')
const showConfig = ref(false)

function statusClass(status) {
  return status === 'degraded' ? 'warning' : status
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

async function refresh() {
  try {
    loading.value = true
    error.value = ''
    const [h, c] = await Promise.all([
      getHealth(),
      getConfig()
    ])
    health.value = h
    config.value = JSON.stringify(c, null, 2)
  } catch (e) {
    error.value = String(e)
    health.value = null
    config.value = null
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<style scoped>
.health-status {
  max-width: 900px;
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
  color: #e53e3e;
}

.section-description {
  color: #718096;
  font-size: 1.1rem;
  margin: 0;
  line-height: 1.5;
}

.actions-section {
  display: flex;
  justify-content: center;
  margin-bottom: 2rem;
}

.refresh-button {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 2rem;
  background: linear-gradient(135deg, #4299e1 0%, #2b6cb0 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 15px rgba(66, 153, 225, 0.3);
  font-family: inherit;
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

.error-message {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.5rem;
  background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
  color: #c53030;
  border-radius: 16px;
  border-left: 4px solid #e53e3e;
  margin-bottom: 2rem;
  box-shadow: 0 4px 15px rgba(229, 62, 62, 0.15);
}

.error-message i {
  font-size: 1.5rem;
  flex-shrink: 0;
  margin-top: 0.2rem;
}

.error-message strong {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 1.1rem;
}

.error-message p {
  margin: 0;
  line-height: 1.4;
}

.health-overview {
  margin-bottom: 2rem;
}

.status-card {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 2rem;
  border-radius: 20px;
  margin-bottom: 2rem;
  border: 2px solid transparent;
  transition: all 0.3s ease;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
}

.status-card.ok {
  background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
  border-color: #68d391;
}

.status-card.error {
  background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
  border-color: #fc8181;
}

.status-card.warning {
  background: linear-gradient(135deg, #fef5e7 0%, #fed7aa 100%);
  border-color: #f6ad55;
}

.status-icon {
  font-size: 3rem;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  backdrop-filter: blur(10px);
}

.status-card.ok .status-icon {
  color: #22543d;
}

.status-card.error .status-icon {
  color: #c53030;
}

.status-card.warning .status-icon {
  color: #c05621;
}

.status-info h3 {
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: #2d3748;
}

.status-text {
  font-size: 1.1rem;
  margin: 0;
  opacity: 0.8;
}

.components-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.component-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem;
  background: white;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
}

.component-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.component-card.healthy {
  border-left: 4px solid #38a169;
}

.component-card.unhealthy {
  border-left: 4px solid #e53e3e;
}

.component-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 50px;
  height: 50px;
  border-radius: 12px;
  font-size: 1.5rem;
  flex-shrink: 0;
}

.component-card.healthy .component-icon {
  background: linear-gradient(135deg, #c6f6d5 0%, #9ae6b4 100%);
  color: #22543d;
}

.component-card.unhealthy .component-icon {
  background: linear-gradient(135deg, #fed7d7 0%, #fbb6ce 100%);
  color: #c53030;
}

.component-info {
  flex: 1;
}

.component-info h4 {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0 0 0.25rem 0;
  color: #2d3748;
}

.component-info p {
  margin: 0 0 0.5rem 0;
  color: #718096;
  font-size: 0.95rem;
}

.model-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: #4a5568;
  background: #f7fafc;
  padding: 0.4rem 0.8rem;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  display: inline-flex;
}

.status-indicator {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.status-indicator.online {
  color: #38a169;
}

.status-indicator.offline {
  color: #e53e3e;
}

.config-section,
.diagnostics-section {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  margin-bottom: 2rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.config-header h3,
.diagnostics-section h3 {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 1.3rem;
  font-weight: 600;
  color: #2d3748;
  margin: 0;
}

.config-header h3 i {
  color: #805ad5;
}

.diagnostics-section h3 i {
  color: #38a169;
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

.config-content {
  margin-top: 1rem;
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
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.diagnostic-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: 12px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.diagnostic-item.pass {
  background: linear-gradient(135deg, #f0fff4 0%, #c6f6d5 100%);
  color: #22543d;
  border: 1px solid #68d391;
}

.diagnostic-item.fail {
  background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
  color: #c53030;
  border: 1px solid #fc8181;
}

.diagnostic-item i {
  font-size: 1.2rem;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .health-status {
    padding: 0 1rem;
  }
  
  .section-title {
    font-size: 1.5rem;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .status-card {
    flex-direction: column;
    text-align: center;
    gap: 1rem;
  }
  
  .component-card {
    flex-direction: column;
    text-align: center;
    gap: 1rem;
  }
  
  .config-header {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }
  
  .components-grid {
    grid-template-columns: 1fr;
  }
  
  .diagnostics-grid {
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  }
}
</style>
