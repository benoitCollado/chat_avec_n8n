export interface User {
  id: number
  email: string
  full_name: string
  created_at: string
}

export interface Message {
  id: number
  author: string
  content: string
  direction: 'user' | 'n8n'
  created_at: string
  user_id: number
}

export interface ChatPayload {
  content: string
  user_id: number
}

export interface ChatPair {
  user: Message
  bot: Message
  raw_webhook_response?: Record<string, unknown>
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  user: User
}

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload extends LoginPayload {
  full_name: string
}

