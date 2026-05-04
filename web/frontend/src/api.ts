import axios from 'axios'

const BASE_URL = (import.meta.env.VITE_API_URL as string) || ''

const api = axios.create({ baseURL: `${BASE_URL}/api` })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// --- Types ---
export interface User {
  id: number
  email: string
  name: string
  topics: string[]
  keywords: string[]
  enabled_sources: string[]
  max_duration_sec: number
  generation_hour: number
  generation_minute: number
}

export interface Segment {
  id: number
  position: number
  title: string
  source_name: string
  summary: string
  audio_url: string
  duration_ms: number
  article_url: string
}

export interface Episode {
  id: number
  date: string
  audio_url: string
  total_duration_ms: number
  summary: string
  status: 'pending' | 'generating' | 'ready' | 'failed'
  created_at: string
  segments: Segment[]
}

export interface Catalog {
  topics: string[]
  keywords: string[]
  sources: { name: string; url: string; topics: string[] }[]
}
