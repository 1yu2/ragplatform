# 服饰图生成 MVP（中文说明）

本项目用于实现以下主流程：

1. 新品图检索爆款 Top-3
2. 将新品图 + Top-3 参考图发送给 Qwen3.5 做风格分析并选择 Top-1
3. 将新品图 + Top-1 + 风格提示词发送给图像模型生成 1 张宣传图

## 当前技术栈

- 后端：FastAPI + SQLModel + SQLite
- 检索：Milvus（HNSW）+ BM25 混合检索（dense:sparse=7:3）
- 模型调用：全部兼容 OpenAI API 形式
  - 风格分析：ModelScope（Qwen/Qwen3.5-397B-A17B）
  - 向量模型：jina-embeddings-v4（图片 embedding）
  - 生图模型：google/gemini-3.1-flash-image-preview
- 前端：React + Vite

## 目录说明

- `app/`：后端代码
- `frontend/`：前端代码
- `config/`：环境配置（base/local/prod）
- `prompts/`：提示词模板
- `data/`：本地数据目录（默认不提交）
- `logs/`：运行日志目录

## 快速启动

### 1) 后端

```bash
cd /Users/fishyuu/idea_project/mul_p2p/generate_image
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
APP_ENV=local uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2) 前端

```bash
cd /Users/fishyuu/idea_project/mul_p2p/generate_image/frontend
npm install
npm run dev
```

访问：

- 前端：`http://127.0.0.1:5173/studio`
- 后端健康检查：`http://127.0.0.1:8000/healthz`

## 准备数据与检索

在 Studio 页面点击“准备数据（已存在则跳过重跑）”：

- 如果 `products.csv`、`new_products.csv`、Milvus 均已有数据，会直接跳过入库
- 否则会执行导入与向量入库（默认 1000 条）

你也可以直接调接口：

```bash
curl -s http://127.0.0.1:8000/api/ingest/status
curl -s 'http://127.0.0.1:8000/api/search/by-new-id?new_id=000000402&top_k=3'
```

## 配置与密钥

- 配置在 `config/*.yaml` 与 `.env` 中读取
- 生产/本地都可通过环境变量覆盖
- **密钥文件不会提交到 Git（`.env*` 已忽略）**

## 参考文档

- `PRD.md`
- `TECH_STACK.md`
- `FRONTEND_GUIDELINES.md`
- `BACKEND_STRUCTURE.md`
- `IMPLEMENTATION_PLAN.md`
- `OPERATIONS.md`
- `progress.txt`
