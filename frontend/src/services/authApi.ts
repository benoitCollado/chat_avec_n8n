import type { LoginPayload, RegisterPayload, TokenPair, User } from '../types'
import { ApiError } from './chatApi'

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class AuthApi {
  private readonly baseUrl: string

  constructor(baseUrl: string = DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  private async request<T>(path: string, options: { method?: string; body?: unknown; token?: string } = {}) {
    const headers: Record<string, string> = {}
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json'
    }
    if (options.token) {
      headers.Authorization = `Bearer ${options.token}`
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      method: options.method ?? 'POST',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })

    if (!response.ok) {
      const message = await response.text()
      throw new ApiError(message || 'Erreur API', response.status)
    }

    return (await response.json()) as T
  }

  register(payload: RegisterPayload) {
    return this.request<TokenPair>('/api/auth/register', { body: payload })
  }

  login(payload: LoginPayload) {
    return this.request<TokenPair>('/api/auth/login', { body: payload })
  }

  refresh(refreshToken: string) {
    return this.request<TokenPair>('/api/auth/refresh', { body: { refresh_token: refreshToken } })
  }

  me(accessToken: string) {
    return this.request<User>('/api/auth/me', { method: 'GET', token: accessToken })
  }
}

