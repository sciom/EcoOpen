<template>
  <div class="login-view">
    <div class="login-card">
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

      <div v-else class="auth-section">
        <div class="tab-navigation">
          <button 
            class="tab-button" 
            :class="{ active: activeTab === 'login' }"
            @click="activeTab = 'login'"
          >
            <i class="fas fa-sign-in-alt"></i> Login
          </button>
          <button 
            class="tab-button" 
            :class="{ active: activeTab === 'register' }"
            @click="activeTab = 'register'"
          >
            <i class="fas fa-user-plus"></i> Register
          </button>
        </div>

        <!-- Login Tab -->
        <div v-if="activeTab === 'login'" class="tab-content">
          <h2 class="title">Welcome Back</h2>
          <p class="subtitle">Sign in to access your analysis dashboard.</p>
          
          <form @submit.prevent="onLogin" class="form">
            <input 
              v-model="loginEmail" 
              type="email" 
              placeholder="email@example.com" 
              class="form-input" 
              required
            />
            <input 
              v-model="loginPassword" 
              type="password" 
              placeholder="Password" 
              class="form-input" 
              required
            />

            <button type="submit" class="submit-button" :disabled="authLoading">
              <i :class="authLoading ? 'fas fa-spinner fa-spin' : 'fas fa-sign-in-alt'"></i>
              {{ authLoading ? 'Signing in...' : 'Login' }}
            </button>
          </form>
        </div>

        <!-- Register Tab -->
        <div v-if="activeTab === 'register'" class="tab-content">
          <h2 class="title">Create Account</h2>
          <p class="subtitle">Join to start analyzing scientific papers.</p>
          
          <form @submit.prevent="onRegister" class="form">
            <input 
              v-model="registerEmail" 
              type="email" 
              placeholder="email@example.com" 
              class="form-input" 
              required
            />
            <input 
              v-model="registerPassword" 
              type="password" 
              placeholder="Password" 
              class="form-input" 
              required
            />
            <input 
              v-model="registerPasswordConfirm" 
              type="password" 
              placeholder="Confirm Password" 
              class="form-input" 
              required
            />

            <!-- Math CAPTCHA -->
            <div class="captcha-section">
              <label class="captcha-label">
                <i class="fas fa-shield-alt"></i>
                Human Verification: What is {{ captchaQuestion }}?
              </label>
              <input 
                v-model="captchaAnswer" 
                type="text" 
                placeholder="Enter answer" 
                class="form-input captcha-input"
                required
              />
              <button type="button" class="refresh-captcha" @click="generateCaptcha">
                <i class="fas fa-sync-alt"></i> Refresh
              </button>
            </div>

            <div v-if="registerHint" class="hint-alert">
              <i class="fas fa-info-circle"></i>
              <div>
                <strong>Requirements</strong>
                <p>{{ registerHint }}</p>
              </div>
            </div>

            <button type="submit" class="submit-button" :disabled="authLoading || !canRegister">
              <i :class="authLoading ? 'fas fa-spinner fa-spin' : 'fas fa-user-plus'"></i>
              {{ authLoading ? 'Creating Account...' : 'Create Account' }}
            </button>
          </form>
        </div>

        <!-- Error Display -->
        <div v-if="authError" class="error-alert">
          <i class="fas fa-exclamation-triangle"></i>
          <div>
            <strong>{{ activeTab === 'login' ? 'Login Error' : 'Registration Error' }}</strong>
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

// Auth state
const authed = ref(isAuthenticated())
const email = ref(getAuthEmail())
const authLoading = ref(false)
const authError = ref('')

// Tab management
const activeTab = ref('login')

// Login form
const loginEmail = ref('')
const loginPassword = ref('')

// Register form
const registerEmail = ref('')
const registerPassword = ref('')
const registerPasswordConfirm = ref('')
const registerHint = ref('')

// Math CAPTCHA
const captchaQuestion = ref('')
const captchaAnswer = ref('')
const correctCaptchaAnswer = ref(0)

function generateCaptcha() {
  const num1 = Math.floor(Math.random() * 10) + 1
  const num2 = Math.floor(Math.random() * 10) + 1
  captchaQuestion.value = `${num1} + ${num2}`
  correctCaptchaAnswer.value = num1 + num2
  captchaAnswer.value = ''
}

function updateRegisterHint() {
  registerHint.value = ''
  if (!registerEmail.value || !registerPassword.value || !registerPasswordConfirm.value) return
  if (registerPassword.value !== registerPasswordConfirm.value) {
    registerHint.value = 'Passwords do not match.'
    return
  }
  if (registerPassword.value.length < 8 || !/[A-Za-z]/.test(registerPassword.value) || !/\d/.test(registerPassword.value)) {
    registerHint.value = 'Password must be at least 8 characters and include letters and numbers.'
  }
}

const canRegister = computed(() => {
  return (
    !!registerEmail.value &&
    !!registerPassword.value &&
    !!registerPasswordConfirm.value &&
    registerPassword.value === registerPasswordConfirm.value &&
    registerPassword.value.length >= 8 && 
    /[A-Za-z]/.test(registerPassword.value) && 
    /\d/.test(registerPassword.value) &&
    captchaAnswer.value === String(correctCaptchaAnswer.value)
  )
})

async function onLogin() {
  try {
    authLoading.value = true
    authError.value = ''
    await login(loginEmail.value, loginPassword.value)
    // Clear login form on success
    loginEmail.value = ''
    loginPassword.value = ''
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
    
    // Verify CAPTCHA
    if (captchaAnswer.value !== String(correctCaptchaAnswer.value)) {
      authError.value = 'Incorrect answer to human verification question.'
      return
    }
    
    await register(registerEmail.value, registerPassword.value, registerPasswordConfirm.value)
    // Clear register form on success
    registerEmail.value = ''
    registerPassword.value = ''
    registerPasswordConfirm.value = ''
    captchaAnswer.value = ''
    generateCaptcha() // Generate new captcha for next use
  } catch (e) {
    authError.value = String(e)
  } finally {
    authLoading.value = false
  }
}

function onLogout() { 
  logout() 
  // Clear all form data on logout
  loginEmail.value = ''
  loginPassword.value = ''
  registerEmail.value = ''
  registerPassword.value = ''
  registerPasswordConfirm.value = ''
  captchaAnswer.value = ''
  generateCaptcha()
}

function goToSettings() { emit('switch-tab', 'settings') }

function updateAuth() {
  authed.value = isAuthenticated()
  email.value = getAuthEmail()
  // Clear sensitive data when auth state changes
  loginPassword.value = ''
  registerPassword.value = ''
  registerPasswordConfirm.value = ''
}

onMounted(() => {
  window.addEventListener(AUTH_EVENT, updateAuth)
  updateAuth()
  generateCaptcha()
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

/* Authenticated state */
.authed-box {
  display: flex; align-items: center; gap: 1rem; padding: 1rem; border-radius: 12px;
  background: linear-gradient(135deg,#f0fff4 0%,#c6f6d5 100%); border: 1px solid #68d391;
}
.authed-info { display: flex; flex-direction: column; gap: .25rem; flex: 1; }

/* Tab Navigation */
.tab-navigation {
  display: flex; gap: 0.5rem; margin-bottom: 2rem;
  background: #f7fafc; padding: 0.25rem; border-radius: 12px;
}
.tab-button {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 0.5rem;
  padding: 0.75rem 1rem; border: none; border-radius: 8px; background: transparent;
  color: #718096; font-weight: 500; cursor: pointer; transition: all 0.2s ease;
}
.tab-button.active {
  background: white; color: #805ad5; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.tab-button:hover:not(.active) { background: rgba(255,255,255,0.5); }

/* Tab Content */
.tab-content { text-align: center; }
.title { display: flex; align-items: center; justify-content: center; gap: .75rem; margin: 0 0 .5rem; }
.subtitle { margin: 0 0 2rem; color: #718096; }
.form { display: flex; flex-direction: column; gap: 1rem; text-align: left; }
.form-input {
  padding: 1rem; border: 2px solid #e2e8f0; border-radius: 12px; background: #f7fafc;
  font-size: 1rem; transition: all 0.2s ease;
}
.form-input:focus { 
  outline: none; border-color: #805ad5; background: white; 
  box-shadow: 0 0 0 3px rgba(128,90,213,.1); 
}

/* CAPTCHA Section */
.captcha-section {
  background: #f7fafc; padding: 1rem; border-radius: 12px; border: 1px solid #e2e8f0;
}
.captcha-label {
  display: flex; align-items: center; gap: 0.5rem; font-weight: 500; color: #4a5568;
  margin-bottom: 0.75rem; font-size: 0.9rem;
}
.captcha-input { margin-bottom: 0.75rem; }
.refresh-captcha {
  display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem;
  background: white; border: 1px solid #e2e8f0; border-radius: 8px;
  color: #718096; font-size: 0.85rem; cursor: pointer; transition: all 0.2s ease;
}
.refresh-captcha:hover { background: #edf2f7; border-color: #cbd5e0; }

/* Buttons */
.submit-button {
  display: flex; align-items: center; justify-content: center; gap: .5rem; 
  padding: 1rem 2rem; border-radius: 12px; border: none; cursor: pointer;
  background: linear-gradient(135deg,#805ad5 0%,#6b46c1 100%); color: white;
  font-size: 1rem; font-weight: 600; transition: all 0.3s ease; margin-top: 1rem;
}
.submit-button:hover:not(:disabled) { 
  transform: translateY(-2px); box-shadow: 0 8px 25px rgba(128,90,213,0.3); 
}
.submit-button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

/* Alerts */
.hint-alert {
  display: flex; gap: 1rem; padding: 1rem; background: linear-gradient(135deg,#FEFCBF 0%,#FAF089 100%);
  color:#744210; border-radius: 12px; border-left: 4px solid #D69E2E; margin-top: 1rem;
}
.error-alert {
  display: flex; gap: 1rem; padding: 1rem; background: linear-gradient(135deg,#fed7d7 0%,#feb2b2 100%);
  color: #c53030; border-radius: 12px; border-left: 4px solid #e53e3e; margin-top: 1.5rem;
}
.error-alert div, .hint-alert div { flex: 1; }
.error-alert strong, .hint-alert strong { display: block; margin-bottom: 0.25rem; }
.error-alert p, .hint-alert p { margin: 0; font-size: 0.9rem; }

/* Actions for authenticated state */
.actions { display: flex; gap: 1rem; flex-wrap: wrap; }
.save-button, .reset-button {
  display: flex; align-items: center; gap: .5rem; padding: .75rem 1.25rem; border-radius: 10px; border: none; cursor: pointer;
}
.save-button { background: linear-gradient(135deg,#38a169 0%,#2f855a 100%); color: white; }
.reset-button { background: #f7fafc; color: #4a5568; border: 1px solid #e2e8f0; }
</style>
