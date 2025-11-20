<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { AuthApi } from './services/authApi'
import { ApiError, ChatApi } from './services/chatApi'
import type { Message, PendingStatus, TokenPair, User } from './types'

// Configuration de marked pour le rendu markdown
marked.setOptions({
  breaks: true, // Convertit les sauts de ligne en <br>
  gfm: true, // Active GitHub Flavored Markdown
})

const authApi = new AuthApi()
const chatApi = new ChatApi()

const messages = ref<Message[]>([])
const loadingHistory = ref(false)
const sending = ref(false)
const errorMessage = ref<string | null>(null)
const pendingReplyId = ref<number | null>(null)
let pendingInterval: number | null = null
let pendingTimeout: number | null = null
const PENDING_TIMEOUT_MS = 60000 // 60 secondes

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
const composerDisabled = computed(() => sending.value || pendingReplyId.value !== null)

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
  pendingReplyId.value = null
  stopPendingPolling()
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
  await resumePendingIfNeeded()
}

const stopPendingPolling = () => {
  if (pendingInterval !== null) {
    clearInterval(pendingInterval)
    pendingInterval = null
  }
  if (pendingTimeout !== null) {
    clearTimeout(pendingTimeout)
    pendingTimeout = null
  }
}

const handlePendingResolution = (status: PendingStatus) => {
  if (status.status === 'completed' && status.bot) {
    const alreadyPresent = messages.value.some((message) => message.id === status.bot!.id)
    if (!alreadyPresent) {
      messages.value = [...messages.value, status.bot]
    }
    pendingReplyId.value = null
    stopPendingPolling()
  } else if (status.status === 'failed') {
    errorMessage.value = "La réponse n'a pas pu être récupérée."
    pendingReplyId.value = null
    stopPendingPolling()
  }
}

const checkPendingStatus = async (pendingId: number) => {
  try {
    const status = await callWithAuth((token) => chatApi.getPendingStatus(pendingId, token))
    handlePendingResolution(status)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      pendingReplyId.value = null
      stopPendingPolling()
    } else {
      console.error(error)
    }
  }
}

const startPendingPolling = (pendingId: number) => {
  pendingReplyId.value = pendingId
  stopPendingPolling()
  checkPendingStatus(pendingId)
  pendingInterval = window.setInterval(() => {
    if (pendingReplyId.value !== null) {
      void checkPendingStatus(pendingId)
    }
  }, 3000)
  
  // Timeout après 60 secondes
  pendingTimeout = window.setTimeout(async () => {
    if (pendingReplyId.value === pendingId) {
      // Marquer le pending comme failed côté backend pour permettre un nouvel envoi immédiat
      try {
        await callWithAuth((token) => chatApi.failPending(pendingId, token))
      } catch (error) {
        console.error('Erreur lors du marquage du pending comme failed:', error)
      }
      errorMessage.value = "La réponse n'est pas arrivée à temps. Veuillez réessayer."
      pendingReplyId.value = null
      stopPendingPolling()
    }
  }, PENDING_TIMEOUT_MS)
}

const resumePendingIfNeeded = async () => {
  if (!accessToken.value || pendingReplyId.value !== null) return
  try {
    const pending = await callWithAuth((token) => chatApi.getPending(token))
    if (!messages.value.some((message) => message.id === pending.user.id)) {
      messages.value = [...messages.value, pending.user]
    }
    startPendingPolling(pending.id)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return
    }
    console.error(error)
  }
}

const sendMessage = async () => {
  if (!chatForm.content.trim() || !accessToken.value || pendingReplyId.value !== null) return
  errorMessage.value = null
  sending.value = true

  try {
    const response = await callWithAuth((token) =>
      chatApi.sendMessage({ content: chatForm.content, user_id: currentUser.value!.id }, token),
    )
    messages.value = [...messages.value, response.user]
    chatForm.content = ''
    startPendingPolling(response.pending_reply_id)
  } catch (error) {
    console.error(error)
    if (error instanceof ApiError) {
      if (error.status === 409) {
        errorMessage.value = 'Veuillez attendre la réponse précédente avant de renvoyer un message.'
      } else if (error.status === 502) {
        // En cas d'erreur 502, le backend a marqué le pending comme failed
        // On réinitialise pour permettre un nouvel envoi immédiat
        pendingReplyId.value = null
        stopPendingPolling()
        errorMessage.value = "L'envoi vers n8n a échoué. Veuillez réessayer."
      } else {
        errorMessage.value = "L'envoi vers n8n a échoué."
      }
    } else {
      errorMessage.value = "L'envoi vers n8n a échoué."
    }
  } finally {
    sending.value = false
  }
}

const logout = () => {
  clearSession()
}

const renderMarkdown = (content: string): string => {
  const html = marked(content)
  // Sanitize et ajouter target="_blank" aux liens pour la sécurité
  const clean = DOMPurify.sanitize(html, {
    ADD_ATTR: ['target'],
  })
  // Ajouter target="_blank" et rel="noopener" aux liens
  return clean.replace(/<a href=/g, '<a target="_blank" rel="noopener noreferrer" href=')
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

onUnmounted(() => {
  stopPendingPolling()
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
            <div v-if="message.direction === 'n8n'" class="message-content" v-html="renderMarkdown(message.content)"></div>
            <p v-else>{{ message.content }}</p>
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
              :disabled="composerDisabled"
            ></textarea>
          </label>
          <button type="submit" :disabled="composerDisabled || !chatForm.content.trim()">
            <span v-if="sending">Envoi…</span>
            <span v-else-if="pendingReplyId">Réponse en attente…</span>
            <span v-else>Envoyer</span>
          </button>
          <p v-if="pendingReplyId" class="info">Veuillez patienter, la réponse arrive…</p>
          <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
        </form>
      </section>
    </section>
  </main>
</template>
