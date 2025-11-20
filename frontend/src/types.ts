export interface Message {
  id: number
  author: string
  content: string
  direction: 'user' | 'n8n'
  created_at: string
}

export interface ChatPayload {
  author: string
  content: string
}

export interface ChatPair {
  user: Message
  bot: Message
  raw_webhook_response?: Record<string, unknown>
}

