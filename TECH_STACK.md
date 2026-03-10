# RAG 管理系统技术栈规范 (TECH_STACK)

## 1. 技术选型总表
| 层级 | 技术 | 说明 |
|---|---|---|
| 前端 | React + Vite + TypeScript + Ant Design | 聊天与管理后台 |
| 后端 | Python + FastAPI | API 与任务编排 |
| 向量库 | Milvus | 稠密向量 + BM25 混合检索 |
| 元数据 | SQLite | 文件、任务、chunk、评估记录 |
| 对象存储 | MinIO | PDF 原文件存储 |
| OCR/版面解析 | Paddle OCR 服务接口 | PDF 版面结构解析 |
| Embedding | 内网 bge-m3 API | 1024 维向量 |
| LLM | DeepSeek Chat API | 流式回答 |
| 评估 | RAGAS | 质量指标评估 |
| 图表 | ECharts | 评估趋势展示 |

## 2. 运行环境
1. 本期默认运行模式: 本地进程启动（非 Docker）。
2. 后端、前端、Milvus、MinIO、模型服务可独立运行。
3. 目标并发: 问答并发 20。

## 3. 外部服务规范
## 3.1 Embedding 服务
- endpoint: `http://192.168.10.60:5001/bge_embed`
- model: `bge-m3`
- auth: 无
- 维度: `1024`
- 请求:
```json
{"model":"bge-m3","input":["hello"]}
```
- 响应:
```json
{"data":[{"embedding":[...], "spare_embedding":{"21":"0.22222"}}]}
```

## 3.2 版面解析服务
- endpoint: `http://192.168.10.60:8888/layout-parsing`
- method: `POST`
- auth: `Authorization: Bearer <TOKEN>`
- 输入 `file` 支持 URL 或直传。

## 3.3 LLM 服务
- endpoint: `https://api.deepseek.com/v1/chat/completions`
- model: `deepseek-chat`
- stream: `true`
- max_tokens: `131072`

## 3.4 MinIO
- endpoint: `192.168.10.60:9000`
- bucket: `rag_sth`
- access_key: 环境变量
- secret_key: 环境变量

## 4. 数据与检索参数
1. 支持语言: 中文。
2. 文档类型: PDF。
3. chunk 参数:
- `chunk_size=2000`（中文字符）
- `chunk_overlap=50`（中文字符）
4. 检索参数:
- `topK=5`
- 融合: 加权融合（向量:BM25 = 0.7:0.3）
5. 拒答阈值:
- `top1 向量相似度 < 0.1` -> `无法回答`

## 5. 配置分层
配置必须分为两套:
1. `local`: 本地开发与联调。
2. `prod`: 生产部署。

建议采用:
- `config/base.yaml`
- `config/local.yaml`
- `config/prod.yaml`
- `.env.local`
- `.env.prod`

## 6. 环境变量清单
以下变量必须存在:
1. `APP_ENV` (`local|prod`)
2. `API_HOST`
3. `API_PORT`
4. `SQLITE_PATH`
5. `MILVUS_HOST`
6. `MILVUS_PORT`
7. `MINIO_ENDPOINT`
8. `MINIO_ACCESS_KEY`
9. `MINIO_SECRET_KEY`
10. `MINIO_BUCKET`
11. `LAYOUT_API_URL`
12. `LAYOUT_API_TOKEN`
13. `EMBEDDING_API_URL`
14. `EMBEDDING_MODEL_NAME`
15. `LLM_API_URL`
16. `LLM_API_KEY`
17. `LLM_MODEL_NAME`
18. `LLM_MAX_TOKENS`
19. `CORS_ALLOW_ORIGINS`

## 7. 安全与密钥规范
1. 禁止在代码中硬编码任何 API key/token。
2. 禁止将密钥写入 SQLite。
3. 日志中禁止打印完整密钥（仅允许后 4 位脱敏显示）。
4. 默认只允许内网访问，严格配置 CORS 白名单。

## 8. 版本建议
1. Python: `3.11`
2. Node.js: `20 LTS`
3. FastAPI: `0.115+`
4. React: `18+`
5. Milvus: `2.4+`
6. SQLite: `3.40+`

## 9. 可替换点（预留）
1. reranker 接口（第二阶段启用）。
2. Docker Compose 部署（第二阶段）。
3. 云部署适配（阿里云，第二阶段）。

