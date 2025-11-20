import type { ChatPayload, ChatPair, Message } from '../types'

const DEFAULT_BASE_URL = 'http://localhost:8000'

export class ChatApi {
  private readonly baseUrl: string

  constructor(baseUrl: string = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  async fetchHistory(limit = 50): Promise<Message[]> {
    const response = await fetch(`${this.baseUrl}/messages?limit=${limit}`)

    if (!response.ok) {
      throw new Error('Erreur lors de la récupération des messages')
    }

    const data = (await response.json()) as { messages: Message[] }
    return data.messages
  }

  async sendMessage(payload: ChatPayload): Promise<ChatPair> {
    const response = await fetch(`${this.baseUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || 'Erreur lors de l’envoi du message')
    }

    return (await response.json()) as ChatPair
  }
}

