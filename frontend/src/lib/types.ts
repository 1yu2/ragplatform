export type SseState = 'queued' | 'retrieving' | 'analyzing' | 'generating' | 'uploading' | 'done' | 'failed'

export type SearchItem = {
  product_id: string
  image_path: string
  preview_url: string
  final_score: number
  dense_score: number
  sparse_score: number
  category: string
  style: string
  season: string
  sales_count: number
  description: string
}

export type SearchResponse = {
  new_id: string
  top_k: number
  count: number
  items: SearchItem[]
}

export type NewProductDetail = {
  new_id: string
  image_path: string
  category: string
  style: string
  season: string
  prompt_hint: string
  preview_url: string
}

export type NewProductListItem = {
  new_id: string
  image_path: string
  category: string
  style: string
  season: string
  prompt_hint: string
  preview_url: string
}

export type NewProductListResponse = {
  count: number
  items: NewProductListItem[]
}

export type GenerateResponse = {
  task_id: string
  status: string
}

export type TaskSummary = {
  task_id: string
  new_id: string
  status: string
  created_at: string
}

export type TaskDetail = {
  task_id: string
  new_id: string
  status: string
  selected_ref_id: string | null
  top3_ref_ids: string | null
  style_prompt: string | null
  final_prompt: string | null
  generated_image_url: string | null
  created_at: string
  updated_at: string
}

export type MetricsSummary = {
  total_tasks: number
  success_rate: number
  dislike_rate: number
}
