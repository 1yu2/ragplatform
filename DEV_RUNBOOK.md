# 开发运行手册 (DEV_RUNBOOK)

## 1. 目录
- 后端: `backend/`
- 前端: `frontend/`

## 2. 后端启动
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash scripts/run_local.sh
```

说明:
- 启动 `main` 会自动初始化 SQLite schema。
- 启动 `main` 会自动初始化 Milvus collection（支持多个）。
- 若 Milvus 初始化失败，服务会启动失败并抛错（避免“看起来启动成功但不可用”）。
- `init_db.py` / `init_milvus.py` 仅用于手动修复。

后端默认地址: `http://localhost:8000`
健康检查: `GET /health`

## 3. 前端启动
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

前端默认地址: `http://localhost:5173`

## 4. 关键环境变量
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `LAYOUT_API_URL`
- `LAYOUT_API_TOKEN`
- `INGEST_PARSE_BATCH_PAGES` (大文档分批解析页数，默认 512)
- `INGEST_MIN_PARSE_BATCH_PAGES` (分批失败时自动二分的最小页数，默认 1)
- `INGEST_SKIP_FAILED_PAGES` (单页仍失败时是否跳过该页继续，默认 true)
- `EMBEDDING_API_URL`
- `EMBEDDING_API_KEY`
- `EMBEDDING_API_AUTH_HEADER`
- `EMBEDDING_API_AUTH_SCHEME`
- `LLM_API_URL`
- `LLM_API_KEY`
- `MILVUS_COLLECTION`
- `MILVUS_COLLECTIONS` (逗号分隔，启动时会全部初始化)

## 5. 常见问题
1. Milvus 连接失败
- 检查 `MILVUS_HOST/MILVUS_PORT`
- 确认 Milvus 服务已启动
- 检查 `MILVUS_COLLECTIONS` 配置是否合法（不能为空、不能包含非法名称）

2. Milvus sparse 索引报错（sparse_vector 无索引）
- 执行 `python scripts/init_milvus.py` 让脚本自动补索引
- 若历史 schema 异常，执行 `python scripts/init_milvus.py --recreate`
- 如需暂时禁用 sparse 字段，设置 `MILVUS_ENABLE_SPARSE=false` 或使用 `--no-sparse`
- 若只修复单个 collection，可执行 `python scripts/init_milvus.py --collection <name>`

3. MinIO 上传失败
- 检查 endpoint 与 bucket 权限
- 确认 access/secret key 正确

4. layout parsing 失败
- 检查 `LAYOUT_API_TOKEN`
- 检查 MinIO 对象 URL 是否可被解析服务访问

5. 聊天无输出
- 检查 `LLM_API_KEY`
- 确认接口支持 `stream=true`

## 6. 当前实现说明
- 已完成端到端 MVP 骨架。
- 评估模块当前为占位实现，后续替换为真实 RAGAS 计算。
- BM25 当前为轻量词匹配补分，后续替换为 Milvus 原生 BM25 检索链路。

## 7. 前端调试（文档解析/Markdown）
### 7.1 调试入口
- 文档预览页: `/kb/files/:fileId/preview`
- 聊天页: `/chat`

### 7.2 预览页调试顺序
1. 先看「原始 Markdown（第 N 页）」是否包含目标内容（例如 `福田`）。
2. 再看右侧「渲染效果（第 N 页）」是否与左侧一致。
3. 对照 `版面块(blocks)`、`逻辑单元(units)`、`向量切分(chunks)` 三张表，确认顺序一致。
4. 必要时点「诊断解析返回」，核对：
- `dataInfo.numPages`
- `layout_results_len`
- `normalized_pages`
- `normalized_blocks`

### 7.3 表格渲染规则（前端）
- Markdown 表格支持半角 `|` 与全角 `｜`。
- 表格行列数不齐时会自动补齐/截断，避免单行错位。
- 单元格内支持基础行内 Markdown（`**粗体**`、`*斜体*`、链接、行内代码）。
- 若出现“某一行显示异常（如 福田）”，优先比较左侧原始 Markdown 与右侧渲染，判断是数据问题还是渲染问题。

### 7.3.1 图像单元说明增强
- `figure` 单元会自动补充：`图像类型`（图表/流程图/地图/图片）与 `图像说明`。
- 图像说明优先由图题与同页邻近正文拼接生成，避免只剩图题。
- 预览页 `units` 表可直接查看 `figure_type` 字段。

### 7.4 聊天页渲染规则
- 回答和引用原文统一走同一套 Markdown 渲染逻辑。
- 引文角标 `[1][2]` 会渲染为上标，可点击展开引用详情。
- 引用内容支持表格/图片/标题等 Markdown 展示。
- 左侧提供聊天历史列表，支持点击回看、删除单条、清空全部（均走后端历史接口）。

### 7.5 大文档诊断建议
- `layout-debug` 返回体可能很大，偶发出现连接被中断（body 未收完）。
- 诊断优先看结构统计字段，不建议长期依赖完整 `raw_preview` 大字段。

### 7.6 大文档批处理解析
- 当 PDF 估算页数 `> INGEST_PARSE_BATCH_PAGES`（默认 512）时，后端会自动按批次分片调用 layout parsing，再合并页码与块结果。
- 若某一批仍返回 500，系统会自动二分该批页数（例如 512→256→128...）直到成功或达到最小页数 `INGEST_MIN_PARSE_BATCH_PAGES`。
- 当前页数判断采用 PDF 实际页数（pypdf 读取），不是正则估算。
- 如果单页仍报 500 且 `INGEST_SKIP_FAILED_PAGES=true`，会跳过该页继续处理其余页面，最终由覆盖率规则决定任务是否成功。
- 若 layout 服务只返回少量页（例如 1~3 页），仍会触发原有覆盖率检查与分片兜底。

### 7.7 聊天历史接口
- `GET /api/v1/chat/history?limit=50&offset=0`：历史列表
- `GET /api/v1/chat/history/{chat_id}`：历史详情
- `DELETE /api/v1/chat/history/{chat_id}`：删除单条
- `DELETE /api/v1/chat/history`：清空历史
