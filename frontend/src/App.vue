<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ChatApi } from './services/chatApi'
import type { Message } from './types'

const api = new ChatApi()
const form = reactive({
  author: 'Utilisateur',
  content: '',
})
const messages = ref<Message[]>([])
const loadingHistory = ref(true)
const sending = ref(false)
const errorMessage = ref<string | null>(null)

const loadHistory = async () => {
  try {
    loadingHistory.value = true
    messages.value = await api.fetchHistory()
  } catch (error) {
    console.error(error)
    errorMessage.value = "Impossible de charger l'historique."
  } finally {
    loadingHistory.value = false
  }
}

const sendMessage = async () => {
  if (!form.content.trim()) return
  errorMessage.value = null
  sending.value = true

  try {
    const response = await api.sendMessage({
      author: form.author,
      content: form.content,
    })

    messages.value = [...messages.value, response.user, response.bot]
    form.content = ''
  } catch (error: unknown) {
    console.error(error)
    errorMessage.value = "L'envoi vers n8n a échoué."
  } finally {
    sending.value = false
  }
}

const formatDate = (value: string) => new Date(value).toLocaleTimeString()

onMounted(loadHistory)
</script>

<template>
  <main>
    <section class="panel">
      <header>
        <div>
          <p class="app-title">Chat Auto n8n</p>
          <p class="subtitle">Historique stocké localement et relayé vers n8n</p>
        </div>
        <button class="ghost" @click="loadHistory" :disabled="loadingHistory">
          Recharger
        </button>
      </header>

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
          Auteur
          <input v-model="form.author" placeholder="Nom affiché" />
        </label>
        <label>
          Message
          <textarea
            v-model="form.content"
            rows="3"
            placeholder="Posez votre question à n8n…"
            :disabled="sending"
          ></textarea>
        </label>
        <button type="submit" :disabled="sending || !form.content.trim()">
          {{ sending ? 'Envoi…' : 'Envoyer' }}
        </button>
        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      </form>
    </section>
  </main>
</template>
