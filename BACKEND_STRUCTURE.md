# BACKEND STRUCTURE

## 1. 目标
后端必须提供从“数据导入”到“检索-分析-生成-存储-审计-反馈”的完整闭环，且全部可在本地运行。

## 2. 推荐目录结构
```text
generate_image/
  app/
    api/
      routes/
        generate.py
        gallery.py
        metrics.py
        ingest.py
      sse.py
    core/
      config.py
      logger.py
      exceptions.py
    models/
      db_models.py
      schemas.py
    services/
      ingest_service.py
      dedup_service.py
      embedding_service.py
      search_service.py
      style_service.py
      generation_service.py
      minio_service.py
      audit_service.py
      feedback_service.py
    repositories/
      task_repo.py
      product_repo.py
      feedback_repo.py
      audit_repo.py
    main.py
  config/
    base.yaml
    local.yaml
    prod.yaml
  logs/
    dedup.log
    app.log
  data/
    products.csv
    new_products.csv
  PRD.md
  TECH_STACK.md
  FRONTEND_GUIDELINES.md
  BACKEND_STRUCTURE.md
  IMPLEMENTATION_PLAN.md
  claude.md
  progress.txt
```

## 3. API 设计（MVP）

### 3.1 导入与预处理
- `POST /api/ingest/products`
  - 功能：扫描爆款目录、生成/更新 `products.csv`、计算去重、入库 Milvus
- `POST /api/ingest/new-products`
  - 功能：扫描新品目录、生成/更新 `new_products.csv`

### 3.2 生成流程
- `POST /api/generate`
  - 输入：
    - `new_id`
    - `aspect_ratio`
    - `user_prompt_override`（可选）
  - 输出：`task_id`

- `GET /api/generate/{task_id}/events` (SSE)
  - 输出事件：`queued/retrieving/analyzing/generating/uploading/done/failed`

### 3.3 历史与反馈
- `GET /api/gallery/tasks`
- `GET /api/gallery/tasks/{task_id}`
- `POST /api/gallery/tasks/{task_id}/feedback`
  - `feedback_type`: `up|down`
  - `feedback_text`: 点踩必填 >=10

### 3.4 指标
- `GET /api/metrics/summary?days=30`

## 4. 数据模型（SQLite）

### 4.1 `tasks`
- `task_id` (PK)
- `session_id`
- `new_id`
- `status`
- `retry_count`
- `selected_ref_id`
- `top3_ref_ids` (JSON)
- `style_prompt`
- `final_prompt`
- `image_model`
- `llm_model`
- `embed_model`
- `latency_ms`
- `sim_warning` (bool)
- `sim_score` (float)
- `created_at`
- `updated_at`

### 4.2 `task_assets`
- `id` (PK)
- `task_id` (FK)
- `asset_type` (`new|ref|generated|raw`)
- `object_key`
- `presigned_url`
- `created_at`

### 4.3 `feedback`
- `id` (PK)
- `task_id` (FK)
- `feedback_type` (`up|down`)
- `feedback_text`
- `created_at`

### 4.4 `audit_logs`
- `id` (PK)
- `task_id`
- `event_type`
- `payload` (JSON)
- `created_at`

## 5. Milvus Schema（`img_all`）
- `product_id` (primary, varchar)
- `image_vector` (float vector, dim=2048)
- `text_sparse_vector` (sparse vector for BM25 pipeline input)
- `category` (varchar, optional)
- `color` (varchar, optional)
- `style` (varchar, optional)
- `season` (varchar, optional)
- `sales_count` (int, default 0)
- `description` (varchar/text)
- `price` (float, default 0)
- `sha256` (varchar)

## 6. 核心流程（严格顺序）

1. `queued`
2. 读取新品图并计算 embedding
3. 混合检索 Top3（Dense+BM25，7:3）
4. 相似度告警检查（新品 vs Top3，阈值 0.7）
5. 命中阈值则 `failed`（阻断）
6. 发送 Top3 给 Qwen：
   - 选 1 张参考图
   - 生成 `style_prompt`
7. 组装最终 prompt 并调用图像生成模型
8. 若接口失败，Qwen 微调 prompt，重试 1 次
9. 上传相关图片到 MinIO
10. 写 `tasks/task_assets/audit_logs`
11. `done` 或 `failed`

## 7. 去重策略
- 触发点：爆款写入 Milvus 前
- 算法：读取图像 bytes，计算 `sha256`
- 规则：首次出现保留，后续重复跳过
- 日志：`/Users/fishyuu/idea_project/mul_p2p/generate_image/logs/dedup.log`

## 8. MinIO 对象路径规则
- `raw/{product_id}.jpg`
- `new/{new_id}.jpg`
- `refs/{task_id}/{product_id}.jpg`
- `generated/{new_id}/{timestamp}.png`

## 9. 审计字段（必须）
- `task_id`
- `new_id`
- `selected_ref_id`
- `top3_ref_ids`
- `style_prompt`
- `final_prompt`
- `image_model`
- `llm_model`
- `embed_model`
- `latency_ms`
- `retry_count`
- `sim_warning`
- `sim_score`
- `status`
- `feedback_type`
- `feedback_text`
- `created_at`

## 10. 错误与降级
- Qwen JSON 解析失败：回退 top1 参考图。
- Qwen 多图分析失败：降级单图分析。
- OpenRouter key 缺失：进入 mock 模式（可配置）。
