<template>
  <div class="login-view">
    <div class="login-card">
      <h2 class="title"><i class="fas fa-sign-in-alt"></i> Sign in</h2>
      <p class="subtitle">Access analysis and settings by signing in.</p>

      <div v-if="authed" class="authed-box">
        <i class="fas fa-user-check"></i>
        <div class="authed-info">
          <strong>{{ email }}</strong>
          <span>You are signed in.</span>
        </div>
        <div class="actions">
          <button class="save-button" @click="goToSettings">
            <i class="fas fa-cog"></i> Go to Settings
          </button>
          <button class="reset-button" @click="onLogout">
            <i class="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
      </div>

      <div v-else class="form">
        <input v-model="email" type="email" placeholder="email@example.com" class="form-input" />
        <input v-model="password" type="password" placeholder="Password" class="form-input" />
        <input v-model="passwordConfirm" type="password" placeholder="Confirm Password (for registration)" class="form-input" />

        <div class="actions">
          <button class="save-button" :disabled="authLoading" @click="onLogin">
            <i :class="authLoading ? 'fas fa-spinner fa-spin' : 'fas fa-sign-in-alt'"></i>
            {{ authLoading ? 'Signing in...' : 'Login' }}
          </button>
          <button class="reset-button" :disabled="authLoading || !canRegister" @click="onRegister">
            <i class="fas fa-user-plus"></i> Register
          </button>
        </div>

        <div v-if="registerHint" class="error-alert" style="background: linear-gradient(135deg,#FEFCBF 0%,#FAF089 100%); color:#744210; border-left-color:#D69E2E;">
          <i class="fas fa-info-circle"></i>
          <div>
            <strong>Registration Requirements</strong>
            <p>{{ registerHint }}</p>
          </div>
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
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { login, register, logout, isAuthenticated, getAuthEmail, AUTH_EVENT } from '../api'

const emit = defineEmits(['switch-tab'])

const authed = ref(isAuthenticated())
const email = ref(getAuthEmail())
const password = ref('')
const passwordConfirm = ref('')
const authLoading = ref(false)
const authError = ref('')
const registerHint = ref('')

function updateRegisterHint() {
  registerHint.value = ''
  if (!email.value || !password.value || !passwordConfirm.value) return
  if (password.value !== passwordConfirm.value) {
    registerHint.value = 'Passwords do not match.'
    return
  }
  if (password.value.length < 8 || !/[A-Za-z]/.test(password.value) || !/\d/.test(password.value)) {
    registerHint.value = 'Password must be at least 8 characters and include letters and numbers.'
  }
}

const canRegister = computed(() => {
  return (
    !!email.value &&
    !!password.value &&
    !!passwordConfirm.value &&
    password.value === passwordConfirm.value &&
    password.value.length >= 8 && /[A-Za-z]/.test(password.value) && /\d/.test(password.value)
  )
})

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
    await register(email.value, password.value, passwordConfirm.value)
  } catch (e) {
    authError.value = String(e)
  } finally {
    authLoading.value = false
  }
}

function onLogout() { logout() }
function goToSettings() { emit('switch-tab', 'settings') }

function updateAuth() {
  authed.value = isAuthenticated()
  email.value = getAuthEmail()
  password.value = ''
}

onMounted(() => {
  window.addEventListener(AUTH_EVENT, updateAuth)
  updateAuth()
})

onBeforeUnmount(() => {
  window.removeEventListener(AUTH_EVENT, updateAuth)
})
</script>

<style scoped>
.login-view { max-width: 520px; margin: 0 auto; }
.login-card {
  background: white; border-radius: 16px; padding: 2rem;
  border: 1px solid #e2e8f0; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
}
.title { display: flex; align-items: center; gap: .75rem; margin: 0 0 .25rem; }
.subtitle { margin: 0 0 1.5rem; color: #718096; }
.form { display: flex; flex-direction: column; gap: 1rem; }
.form-input {
  padding: 1rem; border: 2px solid #e2e8f0; border-radius: 12px; background: #f7fafc;
}
.form-input:focus { outline: none; border-color: #805ad5; background: white; box-shadow: 0 0 0 3px rgba(128,90,213,.1); }
.actions { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: .5rem; }
.save-button, .reset-button {
  display: flex; align-items: center; gap: .5rem; padding: .75rem 1.25rem; border-radius: 10px; border: none; cursor: pointer;
}
.save-button { background: linear-gradient(135deg,#38a169 0%,#2f855a 100%); color: white; }
.reset-button { background: #f7fafc; color: #4a5568; border: 1px solid #e2e8f0; }
.error-alert {
  display: flex; gap: 1rem; padding: 1rem; background: linear-gradient(135deg,#fed7d7 0%,#feb2b2 100%);
  color: #c53030; border-radius: 12px; border-left: 4px solid #e53e3e;
}
.authed-box {
  display: flex; align-items: center; gap: 1rem; padding: 1rem; border-radius: 12px;
  background: linear-gradient(135deg,#f0fff4 0%,#c6f6d5 100%); border: 1px solid #68d391;
}
.authed-info { display: flex; flex-direction: column; gap: .25rem; flex: 1; }
</style>
