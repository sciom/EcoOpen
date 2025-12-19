<template>
  <div class="app-container">
    <header class="header">
      <div class="header-content">
        <div class="logo-section">
          <div class="logo-icon">
            <i class="fas fa-leaf"></i>
          </div>
          <div>
            <h1 class="app-title">EcoOpen LLM</h1>
            <p class="app-subtitle">Scientific PDF Data Extractor</p>
          </div>
        </div>
        <div class="header-right">
          <div class="api-status">
            <i class="fas fa-server"></i>
            <span>{{ apiBase }}</span>
          </div>
          <div class="auth-wrapper">
            <button class="auth-chip" @click="onAuthChipClick">
              <i :class="authed ? 'fas fa-user-check' : 'fas fa-user'" />
              <span>{{ authed ? authEmail : 'Sign in' }}</span>
            </button>
            <div v-if="authed && showAuthMenu" class="auth-menu">
              <button class="auth-menu-item" @click="goToSettings">
                <i class="fas fa-cog"></i> Settings
              </button>
              <button class="auth-menu-item danger" @click="onLogout">
                <i class="fas fa-sign-out-alt"></i> Logout
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <main class="main-content">
      <nav class="tab-navigation">
        <button
          v-for="tabItem in visibleTabs"
          :key="tabItem.id"
          :class="['tab-button', { active: tab === tabItem.id }]"
          @click="onTabClick(tabItem.id)"
        >
          <i :class="tabItem.icon"></i>
          <span>{{ tabItem.label }}</span>
        </button>
      </nav>

      <div class="content-panel">
        <transition name="fade" mode="out-in">
          <section :key="tab" class="tab-content">
            <HealthStatus v-if="tab === 'health'" />
            <BatchAnalyze v-else-if="tab === 'batch'" @switch-tab="onTabClick($event)" />
            <JobsView v-else-if="tab === 'jobs'" />
            <LoginView v-else-if="tab === 'login'" @switch-tab="onTabClick($event)" />
            <SettingsView v-else />
          </section>
        </transition>
      </div>
    </main>

    <footer class="footer">
      <p>&copy; 2025 EcoOpen LLM. Powered by AI for scientific research.</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watchEffect, computed } from 'vue'
import HealthStatus from './components/HealthStatus.vue'
import BatchAnalyze from './components/BatchAnalyze.vue'
import JobsView from './components/JobsView.vue'
import SettingsView from './components/SettingsView.vue'
import LoginView from './components/LoginView.vue'
import { getApiBase, API_BASE_EVENT, isAuthenticated, getAuthEmail, AUTH_EVENT, logout } from './api'

const initialSavedTab = localStorage.getItem('uiTab')
const normalizedInitialTab = (initialSavedTab === 'single') ? 'batch' : initialSavedTab
const tab = ref(isAuthenticated() ? (normalizedInitialTab || 'batch') : 'login')
const apiBase = ref(getApiBase())
const authed = ref(isAuthenticated())
const authEmail = ref(getAuthEmail())
const showAuthMenu = ref(false)

const tabs = [
  { id: 'batch', label: 'Analysis', icon: 'fas fa-layer-group' },
  { id: 'jobs', label: 'Jobs', icon: 'fas fa-list-check' },
  { id: 'health', label: 'System Health', icon: 'fas fa-heartbeat' },
  { id: 'settings', label: 'Settings', icon: 'fas fa-cog' },
  { id: 'login', label: 'Login', icon: 'fas fa-sign-in-alt' }
]

const visibleTabs = computed(() => {
  if (!authed.value) return tabs.filter(t => t.id === 'login')
  return tabs.filter(t => t.id !== 'login')
})

function onTabClick(id) {
  if (!authed.value && id !== 'login') {
    tab.value = 'login'
    return
  }
  const allowed = tabs.map(t => t.id)
  const next = allowed.includes(id) ? id : (authed.value ? 'batch' : 'login')
  tab.value = next
}

const onBaseChange = () => { apiBase.value = getApiBase() }

const onAuthChange = () => {
  const wasAuthed = authed.value
  authed.value = isAuthenticated()
  authEmail.value = getAuthEmail()
  if (authed.value) {
    if (!wasAuthed) {
      tab.value = 'batch'
    }
  } else {
    showAuthMenu.value = false
    if (tab.value !== 'login') {
      tab.value = 'login'
    }
  }
}

function onStorage(e) {
  if (e.key === 'apiBase') onBaseChange()
  if (e.key === 'uiTab' && typeof e.newValue === 'string') onTabClick(e.newValue)
}

onMounted(() => {
  window.addEventListener(API_BASE_EVENT, onBaseChange)
  window.addEventListener(AUTH_EVENT, onAuthChange)
  window.addEventListener('storage', onStorage)
  window.addEventListener('click', onWindowClick)
  onAuthChange()
})

onBeforeUnmount(() => {
  window.removeEventListener(API_BASE_EVENT, onBaseChange)
  window.removeEventListener(AUTH_EVENT, onAuthChange)
  window.removeEventListener('click', onWindowClick)
  window.removeEventListener('storage', onStorage)
})

watchEffect(() => {
  try { localStorage.setItem('uiTab', tab.value) } catch (_) {}
})

function onAuthChipClick() {
  if (authed.value) {
    showAuthMenu.value = !showAuthMenu.value
  } else {
    tab.value = 'login'
  }
}

function goToSettings() {
  tab.value = 'settings'
  showAuthMenu.value = false
}

function onLogout() {
  logout()
  showAuthMenu.value = false
  tab.value = 'login'
}

function onWindowClick(e) {
  const t = e.target
  if (!(t && typeof t.closest === 'function' && t.closest('.auth-wrapper'))) {
    showAuthMenu.value = false
  }
}
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding: 1rem 0;
  position: relative;
  z-index: 100;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.auth-chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.8rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.9);
  cursor: pointer;
}

.auth-chip:hover {
  background: rgba(255, 255, 255, 0.2);
}

.auth-wrapper {
  position: relative;
}

.auth-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 180px;
  background: rgba(255, 255, 255, 0.98);
  color: #111827;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
  padding: 0.25rem;
  z-index: 101;
  backdrop-filter: blur(6px);
}

.auth-menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  border-radius: 8px;
  cursor: pointer;
}

.auth-menu-item:hover {
  background: rgba(0, 0, 0, 0.06);
}

.auth-menu-item i {
  width: 18px;
  text-align: center;
}

.auth-menu-item.danger {
  color: #b91c1c;
}

.auth-menu-item.danger:hover {
  background: rgba(185, 28, 28, 0.08);
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.logo-icon {
  width: 50px;
  height: 50px;
  background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 1.5rem;
  box-shadow: 0 4px 15px rgba(74, 222, 128, 0.3);
}

.app-title {
  margin: 0;
  font-size: 1.8rem;
  font-weight: 700;
  color: white;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.app-subtitle {
  margin: 0;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 400;
}

.api-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(255, 255, 255, 0.1);
  padding: 0.5rem 1rem;
  border-radius: 20px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.85rem;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.main-content {
  flex: 1;
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
  width: 100%;
}

.tab-navigation {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 2rem;
  background: rgba(255, 255, 255, 0.1);
  padding: 0.5rem;
  border-radius: 16px;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  flex-wrap: wrap;
}

.tab-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  font-family: inherit;
  flex: 1;
  min-width: 140px;
  justify-content: center;
}

.tab-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.tab-button:hover::before {
  opacity: 1;
}

.tab-button:hover {
  color: white;
  transform: translateY(-2px);
}

.tab-button.active {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  box-shadow: 0 4px 15px rgba(255, 255, 255, 0.1);
}

.tab-button.active::before {
  opacity: 1;
}

.tab-button i {
  font-size: 1rem;
}

.content-panel {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 20px;
  padding: 2rem;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  min-height: 500px;
}

.tab-content {
  width: 100%;
}

.footer {
  text-align: center;
  padding: 1rem;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
}

.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    text-align: center;
    padding: 0 1rem;
  }

  .main-content {
    padding: 1rem;
  }

  .content-panel {
    padding: 1.5rem;
  }

  .tab-button {
    min-width: auto;
    flex: 1;
    padding: 0.75rem 0.5rem;
  }

  .tab-button span {
    display: none;
  }

  .app-title {
    font-size: 1.5rem;
  }
}

@media (max-width: 480px) {
  .logo-section {
    flex-direction: column;
    gap: 0.5rem;
  }

  .api-status {
    font-size: 0.75rem;
    padding: 0.4rem 0.8rem;
  }
}</style>

