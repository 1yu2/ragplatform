import { apiBaseUrl } from '../lib/api'
import type { SearchItem } from '../lib/types'

export function ReferenceTop3Panel({ items }: { items: SearchItem[] }) {
  return (
    <div className="card">
      <h3>Top-3 参考图</h3>
      {items.length === 0 ? (
        <p className="muted">尚未加载参考图。</p>
      ) : (
        <div className="ref-list">
          {items.map((it, idx) => (
            <div className="ref-item" key={it.product_id}>
              <div className="ref-rank">#{idx + 1}</div>
              <div className="ref-body">
                <img className="ref-preview" src={`${apiBaseUrl}${it.preview_url}`} alt={it.product_id} />
                <div className="ref-title">{it.product_id}</div>
                <div className="ref-meta">分数={it.final_score.toFixed(4)} 稠密={it.dense_score.toFixed(4)} 稀疏={it.sparse_score.toFixed(4)}</div>
                <div className="ref-meta">{it.category} / {it.style} / {it.season}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
