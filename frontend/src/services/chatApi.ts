import type { ChatPayload, ChatQueuedResponse, Message, PendingStatus } from '../types'

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export class ChatApi {
  private readonly baseUrl: string

  constructor(baseUrl: string = DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  private async request<T>(path: string, options: { method?: string; token?: string; body?: unknown } = {}) {
    const headers: Record<string, string> = {}
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json'
    }
    if (options.token) {
      headers.Authorization = `Bearer ${options.token}`
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })

    if (!response.ok) {
      const message = await response.text()
      throw new ApiError(message || 'Erreur API', response.status)
    }

    return (await response.json()) as T
  }

  async fetchHistory(limit = 50, token?: string): Promise<Message[]> {
    const data = await this.request<{ messages: Message[] }>(`/api/messages?limit=${limit}`, { token })
    return data.messages
  }

  async sendMessage(payload: ChatPayload, token?: string): Promise<ChatQueuedResponse> {
    return this.request<ChatQueuedResponse>('/api/chat', {
      method: 'POST',
      body: payload,
      token,
    })
  }

  async getPending(token?: string): Promise<PendingStatus> {
    return this.request<PendingStatus>('/api/chat/pending', { token })
  }

  async getPendingStatus(pendingId: number, token?: string): Promise<PendingStatus> {
    return this.request<PendingStatus>(`/api/chat/pending/${pendingId}`, { token })
  }

  async failPending(pendingId: number, token?: string): Promise<PendingStatus> {
    return this.request<PendingStatus>(`/api/chat/pending/${pendingId}/fail`, {
      method: 'POST',
      token,
    })
  }
}
