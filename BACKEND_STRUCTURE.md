# 后端结构与接口规范 (BACKEND_STRUCTURE)

## 1. 总体架构
后端采用 FastAPI，分为:
1. API 层（HTTP 接口）。
2. 服务层（业务编排）。
3. 仓储层（SQLite + Milvus + MinIO）。
4. 任务层（入库与评估异步任务）。
5. 集成层（Paddle OCR、Embedding、DeepSeek）。

## 2. 推荐目录结构
```text
backend/
  app/
    main.py
    api/
      v1/
        files.py
        chat.py
        evaluation.py
        settings.py
    core/
      config.py
      logging.py
      exceptions.py
      constants.py
    models/
      dto/
        file_dto.py
        chat_dto.py
        eval_dto.py
      entities/
        file_entity.py
        task_entity.py
        chunk_entity.py
        eval_entity.py
    services/
      ingestion_service.py
      parsing_service.py
      chunking_service.py
      embedding_service.py
      retrieval_service.py
      chat_service.py
      evaluation_service.py
    repositories/
      sqlite_repo.py
      milvus_repo.py
      minio_repo.py
    clients/
      layout_client.py
      embedding_client.py
      llm_client.py
    workers/
      task_worker.py
      eval_worker.py
    utils/
      hash_util.py
      text_util.py
      stream_util.py
      timer_util.py
  config/
    base.yaml
    local.yaml
    prod.yaml
  scripts/
    init_db.py
    init_milvus.py
    run_local.sh
```

## 3. 配置结构
`config/base.yaml` 至少包含:
1. app
2. sqlite
3. milvus
4. minio
5. layout_api
6. embedding_api
7. llm_api
8. retrieval
9. evaluation
10. cors

示例:
```yaml
app:
  env: local
  host: 0.0.0.0
  port: 8000
  first_token_timeout_sec: 10

retrieval:
  top_k: 5
  dense_weight: 0.7
  bm25_weight: 0.3
  refuse_threshold: 0.1

chunking:
  method: semantic
  chunk_size: 2000
  overlap: 50
  sentence_safe: true
```

## 4. SQLite 数据表定义
## 4.1 files
1. `id` TEXT PK
2. `file_name` TEXT
3. `sha256` TEXT UNIQUE
4. `size_bytes` INTEGER
5. `minio_object_key` TEXT
6. `status` TEXT
7. `created_at` DATETIME
8. `updated_at` DATETIME

## 4.2 ingest_tasks
1. `id` TEXT PK
2. `file_id` TEXT
3. `status` TEXT (`QUEUED|RUNNING|SUCCESS|FAILED`)
4. `retry_count` INTEGER
5. `error_message` TEXT
6. `started_at` DATETIME
7. `finished_at` DATETIME

## 4.3 chunks
1. `id` TEXT PK
2. `file_id` TEXT
3. `page` INTEGER
4. `paragraph_id` TEXT
5. `block_type` TEXT
6. `chunk_index` INTEGER
7. `chunk_text` TEXT
8. `source_offset` INTEGER
9. `metadata_json` TEXT

## 4.4 chat_logs
1. `id` TEXT PK
2. `question` TEXT
3. `rewritten_question` TEXT
4. `answer` TEXT
5. `is_refused` INTEGER
6. `top1_score` REAL
7. `latency_first_token_ms` INTEGER
8. `created_at` DATETIME

## 4.5 evaluations
1. `id` TEXT PK
2. `dataset_size` INTEGER
3. `faithfulness` REAL
4. `answer_relevancy` REAL
5. `context_precision` REAL
6. `context_recall` REAL
7. `overall_score` REAL
8. `status` TEXT
9. `created_at` DATETIME

## 5. Milvus 集合定义
集合名建议: `rag_chunks`

字段:
1. `chunk_id` (primary key, VARCHAR)
2. `file_id` (VARCHAR)
3. `file_name` (VARCHAR)
4. `page` (INT64)
5. `paragraph_id` (VARCHAR)
6. `block_type` (VARCHAR)
7. `chunk_text` (VARCHAR / dynamic field)
8. `dense_vector` (FLOAT_VECTOR, dim=1024)
9. `sparse_vector` (SPARSE_FLOAT_VECTOR，来自 `spare_embedding`)

索引:
1. dense 向量索引（按 Milvus 推荐）
2. sparse BM25 索引

## 6. API 规范
## 6.1 文件接口
1. `POST /api/v1/files/upload`
- 入参: multipart/form-data (`file`)
- 出参: file_id + task_id
2. `GET /api/v1/files`
- 出参: 文件列表与状态
3. `GET /api/v1/files/{file_id}/preview`
- 出参: 版面块 + chunk 预览
4. `POST /api/v1/files/{file_id}/reprocess`
- 失败任务重跑

## 6.2 聊天接口
1. `POST /api/v1/chat/stream`
- 入参: `question`
- 出参: SSE 流
- 结束帧包含:
  - citations
  - top1_score
  - is_refused

## 6.3 评估接口
1. `POST /api/v1/evaluation/run`
2. `GET /api/v1/evaluation/latest`
3. `GET /api/v1/evaluation/history`

## 6.4 配置接口
1. `GET /api/v1/settings/runtime`
- 返回脱敏配置

## 7. 关键业务逻辑定义
## 7.1 去重
1. 上传后先算 SHA256。
2. 若已存在，直接返回已有 file_id，不再入库。

## 7.2 问题改写触发
1. 问题长度 >= 35 字符，触发。
2. 或命中模糊词模式，触发。
3. 改写失败回退原问题。

## 7.3 拒答逻辑
1. 取检索结果 top1 的向量相似度。
2. 若 `<0.1`，返回 `无法回答`。
3. 同时返回最近 5 条片段。

## 7.4 引用格式
统一格式:
`[文件名-页码-段落ID]`

## 8. 任务执行模型
1. 上传接口只创建任务并快速返回。
2. 后台 worker 轮询 `QUEUED` 任务。
3. 每个任务步骤:
- 解析
- 标准化
- 过滤
- 切分
- embedding
- 入库
4. 任一步骤失败则重试，累计 3 次后标记 `FAILED`。

## 9. 日志与追踪
日志字段最少包含:
1. `request_id`
2. `task_id`
3. `file_id`
4. `step`
5. `duration_ms`
6. `status`
7. `error_message`

## 10. 测试建议
1. 单元测试:
- hash 去重
- chunk 规则
- 拒答规则
2. 集成测试:
- 上传到入库全链路
- 聊天流式返回
- 评估任务运行
3. 回归测试:
- 指标计算稳定性
- 前后端接口兼容性

