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

export interface ChatQueuedResponse {
  user: Message
  pending_reply_id: number
}

export interface PendingStatus {
  id: number
  status: 'pending' | 'completed' | 'failed'
  user: Message
  bot?: Message
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

