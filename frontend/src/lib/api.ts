import type {
  GenerateResponse,
  MetricsSummary,
  NewProductDetail,
  NewProductListResponse,
  SearchResponse,
  TaskDetail,
  TaskSummary,
} from './types'

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status} ${path}: ${text || res.statusText}`)
  }
  return (await res.json()) as T
}

export const api = {
  async ingestStatus() {
    return http<{
      products_csv_rows: number
      new_products_csv_rows: number
      milvus_collection_exists: boolean
      milvus_entity_count: number
      ready: boolean
    }>('/api/ingest/status')
  },
  async ingestProducts(limit = 1000) {
    return http(`/api/ingest/products?limit=${limit}`, { method: 'POST' })
  },
  async ingestNewProducts(limit = 1000) {
    return http(`/api/ingest/new-products?limit=${limit}`, { method: 'POST' })
  },
  async initMilvus() {
    return http('/api/ingest/milvus/init', { method: 'POST' })
  },
  async ingestMilvusProducts(limit = 1000, batchSize = 32) {
    return http(`/api/ingest/milvus/products?limit=${limit}&batch_size=${batchSize}`, { method: 'POST' })
  },
  async searchByNewId(newId: string, topK = 3) {
    return http<SearchResponse>(`/api/search/by-new-id?new_id=${encodeURIComponent(newId)}&top_k=${topK}`)
  },
  async listNewProducts(limit = 200) {
    return http<NewProductListResponse>(`/api/catalog/new-products?limit=${limit}`)
  },
  async getNewProduct(newId: string) {
    return http<NewProductDetail>(`/api/catalog/new-products/${encodeURIComponent(newId)}`)
  },
  async generate(payload: { new_id: string; aspect_ratio: string; user_prompt_override?: string; session_id?: string }) {
    return http<GenerateResponse>('/api/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  async listTasks() {
    return http<TaskSummary[]>('/api/gallery/tasks')
  },
  async getTask(taskId: string) {
    return http<TaskDetail>(`/api/gallery/tasks/${taskId}`)
  },
  async submitFeedback(taskId: string, feedbackType: 'up' | 'down', feedbackText = '') {
    return http(`/api/gallery/tasks/${taskId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ feedback_type: feedbackType, feedback_text: feedbackText }),
    })
  },
  async metrics(days = 30) {
    return http<MetricsSummary>(`/api/metrics/summary?days=${days}`)
  },
}

export const apiBaseUrl = BASE
