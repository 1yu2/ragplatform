# TECH STACK

## 1. 目标技术栈（冻结）

### 前端
- React 18
- Vite
- TailwindCSS
- shadcn/ui
- SSE (EventSource) 实时任务进度

### 后端
- FastAPI
- SQLModel + SQLite（MVP）
- Uvicorn

### 数据与存储
- Milvus（公司环境）
  - Host: `192.168.10.54`
  - Port: `19530`
  - Collection: `img_all`
  - Vector dim: `2048`
  - Metric: `COSINE`
  - Index: `HNSW`
- MinIO
  - Endpoint: `192.168.10.60:9000`
  - Bucket: `img-all`
  - Presigned URL: `60s`
  - `secure=false`

### AI 模型与网关
- Embedding（OpenRouter）：
  - `jina-embeddings-v4`
- LLM（ModelScope OpenAI-compatible）：
  - `Qwen/Qwen3.5-397B-A17B`
- Image Generation（OpenRouter）：
  - `google/gemini-3.1-flash-image-preview`

## 2. 关键算法策略

### 2.1 混合检索
- Dense + BM25
- 固定权重：`dense=0.7`，`sparse=0.3`
- 不做类目约束过滤
- TopK：`3`

建议统一打分公式：
```text
final_score = 0.7 * dense_score + 0.3 * sparse_score
```

### 2.2 参考图选择
- 输入：检索 Top3
- Qwen 输出固定 JSON：
```json
{
  "selected_product_id": "SKU001",
  "style_prompt": "....",
  "reason": "...."
}
```
- 如果 JSON 非法：回退为 `top1` 结果。

### 2.3 相似度告警（阻断）
- 比较对象：新品图 vs 检索 Top3
- 指标：embedding cosine similarity
- 阈值：`>= 0.7`
- 触发动作：终止任务并返回错误，不继续生成。

### 2.4 失败重试
- 总尝试次数：最多 2 次（首次 + 1 次重试）
- 仅接口报错触发重试
- 第二次 prompt 由 Qwen 改写

## 3. 配置体系（必须独立）

建议文件布局：
```text
config/
  base.yaml
  local.yaml
  prod.yaml
.env.local
.env.prod
```

### 3.1 必须参数
- `APP_ENV` = `local|prod`
- `OPENROUTER_API_KEY`
- `MODELSCOPE_API_KEY`
- `MILVUS_HOST`
- `MILVUS_PORT`
- `MILVUS_COLLECTION`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_BUCKET`
- `MINIO_SECURE`
- `MINIO_USE_PRESIGNED_URL`
- `MINIO_PRESIGNED_EXPIRE_SECONDS=60`
- `DATA_BESTSELLER_DIR=/Users/fishyuu/idea_project/mul_p2p/fashion_img`
- `DATA_NEW_DIR=/Users/fishyuu/idea_project/mul_p2p/product`
- `ENABLE_MOCK=true|false`

### 3.2 Mock 规则
- 无 OpenRouter Key 时默认 `ENABLE_MOCK=true`
- 一旦 key 配置存在且开关关闭，自动走真实模型调用

## 4. 当前阶段明确不使用
- Redis
- Celery
- PostgreSQL
- 登录鉴权系统
- 多模型切换能力

## 5. 安全要求
- 禁止在代码库提交真实 API Key。
- Token 只放 `.env.*`，并确保 `.gitignore` 覆盖。
