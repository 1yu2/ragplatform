# Operations Guide

## 1. 当前状态
- 前端页面：`/studio`、`/gallery`、`/metrics`
- Studio 支持：新品下拉选择 + 新品图片预览 + Top-3 参考图预览
- 后端链路：`ingest -> search -> qwen style -> image generate -> gallery`
- 所有模型调用均为 OpenAI-compatible 形式
- `ENABLE_MOCK=true`：用新品原图复制为生成图（联调快速模式）
- `ENABLE_MOCK=false`：真实调用 Qwen + 图像模型

## 2. 目录与数据
- 项目目录：`/Users/fishyuu/idea_project/mul_p2p/generate_image`
- 爆款图目录：`/Users/fishyuu/idea_project/mul_p2p/fashion_img`
- 新品图目录：`/Users/fishyuu/idea_project/mul_p2p/product`
- 生成图目录：`/Users/fishyuu/idea_project/mul_p2p/generate_image/data/generated`

## 3. 配置

### 3.1 核心配置文件
- `config/base.yaml`
- `config/local.yaml`
- `config/prod.yaml`
- `.env.local`
- `.env.prod`

说明：后端会自动加载 `.env.<APP_ENV>`，无需手工 `source`。

### 3.2 真实测试必须项
在 `.env.local` 填写：

```env
APP_ENV=local
ENABLE_MOCK=false

# Qwen (ModelScope OpenAI-compatible)
MODELSCOPE_BASE_URL=https://api-inference.modelscope.cn/v1
MODELSCOPE_API_KEY=你的_key
MODELSCOPE_LLM_MODEL=Qwen/Qwen3.5-397B-A17B

# Embedding / Image (OpenRouter 或兼容网关)
OPENROUTER_BASE_URL=你的_openai_兼容_base_url
OPENROUTER_API_KEY=你的_key
OPENROUTER_EMBEDDING_MODEL=jina-embeddings-v4
OPENROUTER_IMAGE_MODEL=google/gemini-3.1-flash-image-preview

# 数据路径
DATA_BESTSELLER_DIR=/Users/fishyuu/idea_project/mul_p2p/fashion_img
DATA_NEW_DIR=/Users/fishyuu/idea_project/mul_p2p/product
DATA_PRODUCTS_CSV_PATH=/Users/fishyuu/idea_project/mul_p2p/generate_image/data/products.csv
DATA_NEW_PRODUCTS_CSV_PATH=/Users/fishyuu/idea_project/mul_p2p/generate_image/data/new_products.csv
DATA_GENERATED_DIR=/Users/fishyuu/idea_project/mul_p2p/generate_image/data/generated
```

## 4. 启动

### 4.1 后端
```bash
cd /Users/fishyuu/idea_project/mul_p2p/generate_image
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
APP_ENV=local uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4.2 前端
```bash
cd /Users/fishyuu/idea_project/mul_p2p/generate_image/frontend
npm install
npm run dev
```

访问：
- 前端：`http://127.0.0.1:5173/studio`
- 健康检查：`http://127.0.0.1:8000/healthz`

## 5. 真实测试（建议顺序）

### 5.1 检查模式
```bash
curl -s http://127.0.0.1:8000/healthz
```
期待：`"mock": false`

### 5.2 导入调试数据（先 1000 条）
```bash
curl -s -X POST 'http://127.0.0.1:8000/api/ingest/products?limit=1000'
curl -s -X POST 'http://127.0.0.1:8000/api/ingest/new-products?limit=1000'
curl -s -X POST 'http://127.0.0.1:8000/api/ingest/milvus/init'
curl -s -X POST 'http://127.0.0.1:8000/api/ingest/milvus/products?limit=1000&batch_size=32'
```
说明：当前向量为图片 embedding。首次切换 embedding 模型或向量管线版本时，会自动重建一次；之后未变化数据会自动跳过。

### 5.3 检索验证
```bash
curl -s 'http://127.0.0.1:8000/api/search/by-new-id?new_id=000000402&top_k=3'
```

### 5.4 发起真实生成
```bash
curl -s -X POST http://127.0.0.1:8000/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"new_id":"000000402","aspect_ratio":"3:4","session_id":"sess_real","user_prompt_override":""}'
```

### 5.5 查状态与结果
```bash
# 事件流
curl -N 'http://127.0.0.1:8000/api/generate/<task_id>/events'

# 任务详情（含 generated_image_url）
curl -s 'http://127.0.0.1:8000/api/gallery/tasks/<task_id>'
```

## 6. 常见问题

1. `API key is empty`
- 原因：`.env.local` 的 key 未填，或 key 名写错。
- 处理：补齐 `MODELSCOPE_API_KEY` / `OPENROUTER_API_KEY`，重启后端。

2. 前端 `Failed to fetch`
- 原因：后端未启动、端口错误、或跨域预检失败。
- 处理：确认后端在 `127.0.0.1:8000`；当前已启用 CORS，`OPTIONS` 应返回 200。

3. 生成失败但有 task_id
- 原因：`/api/generate` 为同步任务创建接口，失败信息写入后端日志与审计。
- 处理：查看后端日志、`/api/generate/{task_id}/events`、`/api/gallery/tasks/{task_id}`。

4. 检索 Top-3 总是相同
- 原因：常见是向量尚未成功入库，或 embedding 厂商不支持当前图片输入格式。
- 处理：先执行 5.2 的 Milvus 初始化与向量入库；若仍失败，检查 embedding 接口返回错误并确认模型支持图片 embeddings。

## 7. 提示词样例（可直接粘贴到 Studio）

1. 通用电商主图
- `高质感电商服饰主图，保持原服装版型和颜色不变，模特自然站姿，柔和棚拍光，背景简洁干净，突出面料细节与轮廓，禁止文字和水印。`

2. 针织上衣
- `秋冬针织上衣商业宣传图，主体服装不可改款改色，强调织纹与垂感，暖色调氛围光，背景极简，突出上半身穿搭效果。`

3. 长裙连衣裙
- `女装连衣裙主图，保留裙摆结构和花纹细节，构图包含全身，轻户外自然光，背景虚化但不喧宾夺主，质感真实。`

4. 鞋靴类
- `女鞋电商广告图，鞋型和材质严格保持一致，低角度质感拍摄，干净地面反射，重点展示鞋面纹理和轮廓，品牌无水印。`

5. 包袋类
- `包袋电商主图，保持五金与皮质细节一致，半身穿搭场景，干净背景，光线均匀，突出容量感和立体轮廓。`

6. 极简白底图
- `白底高端商品图，主体居中，边缘清晰，均匀柔光，颜色准确，细节真实，无额外元素，无文字。`

7. 轻生活场景
- `生活化轻场景服饰图，保留服装主体细节，背景简洁有层次，色彩克制，画面干净，适合跨境平台主图。`

8. 失败重试优化
- `请优化构图与光线，确保服装主体完整、贴合新品原图，减少背景干扰，提升材质真实感与商业展示效果。`
