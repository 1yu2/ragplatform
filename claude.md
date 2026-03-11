# claude.md

本文件是本项目的主配置规范（浓缩规则）。详细内容以以下文档为准：
- `PRD.md`
- `TECH_STACK.md`
- `FRONTEND_GUIDELINES.md`
- `BACKEND_STRUCTURE.md`
- `IMPLEMENTATION_PLAN.md`
- `progress.txt`
- `OPERATIONS.md`

## 1) 技术栈摘要
- Frontend: React18 + Vite + Tailwind + shadcn/ui + SSE
- Backend: FastAPI + SQLModel + SQLite
- Vector DB: Milvus (`192.168.10.54:19530`, collection=`img_all`, dim=2048, COSINE, HNSW)
- Object Storage: MinIO (`img-all`, presigned=60s)
- LLM: ModelScope `Qwen/Qwen3.5-397B-A17B`
- Embedding: OpenRouter `jina-embeddings-v4`
- Image Gen: OpenRouter `google/gemini-3.1-flash-image-preview`
- 检索策略：Dense/BM25 = `7:3`, Top3
- 相似度阻断阈值：`0.7`（命中即失败）

## 2) 命名约定
- Python 文件：`snake_case.py`
- 组件文件：`PascalCase.tsx`
- Hook 文件：`useXxx.ts`
- API 路由：`/api/<domain>/<action>`
- 数据 ID：
  - `product_id` = 文件名去后缀
  - `new_id` = 文件名去后缀
  - 冲突时自动加目录前缀

## 3) 文件结构
```text
app/
  api/routes/
  services/
  repositories/
  models/
  core/
config/
logs/
data/
```

强制路径：
- 爆款库：`/Users/fishyuu/idea_project/mul_p2p/fashion_img`
- 新品库：`/Users/fishyuu/idea_project/mul_p2p/product`
- 去重日志：`/Users/fishyuu/idea_project/mul_p2p/generate_image/logs/dedup.log`

## 4) 组件模式
- 页面仅三页：`/studio`、`/gallery`、`/metrics`
- 无登录，基于本地 `session_id`
- SSE 事件固定：
  - `queued/retrieving/analyzing/generating/uploading/done/failed`
- 点踩反馈必填且 >=10 字；点赞可选备注；可修改反馈

## 5) 禁止操作
1. 禁止提交真实 API Key/Token 到仓库。
2. 禁止绕过相似度阻断逻辑（阈值 0.7）。
3. 禁止在本期引入未批准技术栈（如 Celery/Redis/登录系统）。
4. 禁止擅自修改检索权重（7:3）和 TopK（3）。
5. 禁止删除审计字段或跳过审计记录。
6. 禁止跳过 `progress.txt` 更新。

## 6) 进度规则
- 每完成一个功能，必须同步更新 `progress.txt`：
  - 已完成项（含日期）
  - 待办项
  - 阻塞项与原因
