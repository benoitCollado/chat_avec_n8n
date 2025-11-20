<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { AuthApi } from './services/authApi'
import { ApiError, ChatApi } from './services/chatApi'
import type { Message, TokenPair, User } from './types'

const authApi = new AuthApi()
const chatApi = new ChatApi()

const messages = ref<Message[]>([])
const loadingHistory = ref(false)
const sending = ref(false)
const errorMessage = ref<string | null>(null)

const accessToken = ref<string | null>(localStorage.getItem('accessToken'))
const refreshToken = ref<string | null>(localStorage.getItem('refreshToken'))
const currentUser = ref<User | null>(null)

const authMode = ref<'login' | 'register'>('login')
const authLoading = ref(false)
const authError = ref<string | null>(null)
const authForm = reactive({
  full_name: '',
  email: '',
  password: '',
})

const chatForm = reactive({
  content: '',
})

const isAuthenticated = computed(() => Boolean(accessToken.value && currentUser.value))

const persistSession = (tokens: TokenPair) => {
  accessToken.value = tokens.access_token
  refreshToken.value = tokens.refresh_token
  currentUser.value = tokens.user
  localStorage.setItem('accessToken', tokens.access_token)
  localStorage.setItem('refreshToken', tokens.refresh_token)
}

const clearSession = () => {
  accessToken.value = null
  refreshToken.value = null
  currentUser.value = null
  messages.value = []
  localStorage.removeItem('accessToken')
  localStorage.removeItem('refreshToken')
}

const refreshSession = async () => {
  if (!refreshToken.value) return
  try {
    const tokens = await authApi.refresh(refreshToken.value)
    persistSession(tokens)
  } catch (error) {
    console.error(error)
    clearSession()
  }
}

const handleAuthSubmit = async () => {
  authError.value = null
  authLoading.value = true
  try {
    const payload =
      authMode.value === 'register'
        ? { full_name: authForm.full_name, email: authForm.email, password: authForm.password }
        : { email: authForm.email, password: authForm.password }

    const response =
      authMode.value === 'register'
        ? await authApi.register(payload)
        : await authApi.login(payload)

    persistSession(response)
    await loadHistory()
  } catch (error) {
    console.error(error)
    authError.value = "Impossible d'authentifier l'utilisateur."
  } finally {
    authLoading.value = false
  }
}

const callWithAuth = async <T>(fn: (token: string) => Promise<T>): Promise<T> => {
  if (!accessToken.value) {
    throw new Error('Non authentifié')
  }
  try {
    return await fn(accessToken.value)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401 && refreshToken.value) {
      await refreshSession()
      if (!accessToken.value) {
        throw error
      }
      return fn(accessToken.value)
    }
    throw error
  }
}

const loadHistory = async () => {
  if (!accessToken.value) return
  loadingHistory.value = true
  errorMessage.value = null
  try {
    messages.value = await callWithAuth((token) => chatApi.fetchHistory(50, token))
  } catch (error) {
    console.error(error)
    errorMessage.value = "Impossible de charger l'historique."
  } finally {
    loadingHistory.value = false
  }
}

const sendMessage = async () => {
  if (!chatForm.content.trim() || !accessToken.value) return
  errorMessage.value = null
  sending.value = true

  try {
    const response = await callWithAuth((token) =>
      chatApi.sendMessage({ content: chatForm.content, user_id: currentUser.value!.id }, token),
    )
    messages.value = [...messages.value, response.user, response.bot]
    chatForm.content = ''
  } catch (error) {
    console.error(error)
    errorMessage.value = "L'envoi vers n8n a échoué."
  } finally {
    sending.value = false
  }
}

const logout = () => {
  clearSession()
}

const formatDate = (value: string) => new Date(value).toLocaleTimeString()

onMounted(async () => {
  if (accessToken.value && refreshToken.value) {
    try {
      const user = await authApi.me(accessToken.value)
      currentUser.value = user
      await loadHistory()
    } catch (error) {
      console.warn('Access token invalide, tentative de refresh…')
      await refreshSession()
    }
  }
})
</script>

<template>
  <main>
    <section class="panel">
      <header>
        <div>
          <p class="app-title">Chat Auto n8n</p>
          <p class="subtitle">Historique stocké localement et relayé vers n8n</p>
        </div>
        <div class="actions">
          <button class="ghost" v-if="isAuthenticated" @click="loadHistory" :disabled="loadingHistory">
            Recharger
          </button>
          <button class="ghost danger" v-if="isAuthenticated" @click="logout">Déconnexion</button>
        </div>
      </header>

      <section v-if="!isAuthenticated" class="auth-panel">
        <div class="auth-tabs">
          <button :class="{ active: authMode === 'login' }" @click="authMode = 'login'">Connexion</button>
          <button :class="{ active: authMode === 'register' }" @click="authMode = 'register'">Inscription</button>
        </div>
        <form class="auth-form" @submit.prevent="handleAuthSubmit">
          <label v-if="authMode === 'register'">
            Nom complet
            <input v-model="authForm.full_name" placeholder="Jane Doe" required />
          </label>
          <label>
            Email
            <input type="email" v-model="authForm.email" placeholder="vous@exemple.com" required />
          </label>
          <label>
            Mot de passe
            <input type="password" v-model="authForm.password" placeholder="********" minlength="8" required />
          </label>
          <button type="submit" :disabled="authLoading">
            {{ authLoading ? 'Chargement…' : authMode === 'login' ? 'Se connecter' : "S'inscrire" }}
          </button>
          <p v-if="authError" class="error">{{ authError }}</p>
        </form>
      </section>

      <section v-else class="chat-wrapper">
        <div class="user-banner">
          <p>Connecté en tant que <strong>{{ currentUser?.full_name }}</strong></p>
          <small>{{ currentUser?.email }}</small>
        </div>

        <div class="history" v-if="messages.length">
          <article v-for="message in messages" :key="message.id" class="bubble" :class="message.direction">
            <div class="bubble-header">
              <span class="author">{{ message.author }}</span>
              <time>{{ formatDate(message.created_at) }}</time>
            </div>
            <p>{{ message.content }}</p>
          </article>
        </div>

        <p v-else-if="!loadingHistory" class="empty">Aucun message pour le moment.</p>
        <p v-else class="empty">Chargement de l’historique…</p>

        <form class="composer" @submit.prevent="sendMessage">
          <label>
            Message
            <textarea
              v-model="chatForm.content"
              rows="3"
              placeholder="Posez votre question à n8n…"
              :disabled="sending"
            ></textarea>
          </label>
          <button type="submit" :disabled="sending || !chatForm.content.trim()">
            {{ sending ? 'Envoi…' : 'Envoyer' }}
          </button>
          <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
        </form>
      </section>
    </section>
  </main>
</template>
