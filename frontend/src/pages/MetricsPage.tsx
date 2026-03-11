import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { MetricsSummary } from '../lib/types'

export function MetricsPage() {
  const [summary, setSummary] = useState<MetricsSummary | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.metrics(30)
      .then((v) => {
        setSummary(v)
        setError('')
      })
      .catch((e) => setError((e as Error).message))
  }, [])

  return (
    <div className="metrics-grid">
      <div className="metric-card">
        <div className="metric-label">30天总任务数</div>
        <div className="metric-value">{summary?.total_tasks ?? '-'}</div>
      </div>
      <div className="metric-card">
        <div className="metric-label">成功率</div>
        <div className="metric-value">{summary ? `${(summary.success_rate * 100).toFixed(2)}%` : '-'}</div>
      </div>
      <div className="metric-card">
        <div className="metric-label">点踩率</div>
        <div className="metric-value">{summary ? `${(summary.dislike_rate * 100).toFixed(2)}%` : '-'}</div>
      </div>
      {error && <p className="err">{error}</p>}
    </div>
  )
}
