import type { NewProductDetail } from '../lib/types'
import { apiBaseUrl } from '../lib/api'

type Props = {
  product: NewProductDetail | null
}

export function NewProductPreview({ product }: Props) {
  return (
    <div className="card">
      <h3>新品预览</h3>
      {!product ? (
        <p className="muted">请选择新品，系统会展示该产品图片与基础信息。</p>
      ) : (
        <div>
          <div className="ref-meta">new_id: {product.new_id}</div>
          <div className="ref-meta">分类: {product.category} / 风格: {product.style} / 季节: {product.season}</div>
          <img className="product-preview" src={`${apiBaseUrl}${product.preview_url}`} alt={product.new_id} />
        </div>
      )}
    </div>
  )
}
