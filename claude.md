# CLAUDE.md

本文件是 `PRD.md`、`APP_FLOW.md`、`TECH_STACK.md`、`FRONTEND_GUIDELINES.md`、`BACKEND_STRUCTURE.md`、`IMPLEMENTATION_PLAN.md` 的浓缩执行规则。实现时以本文件为高优先级速查规范，冲突时以原始 6 文档为准。

## 1) 技术栈摘要
- 前端: `React + Vite + TypeScript + Ant Design + ECharts`
- 后端: `Python 3.11 + FastAPI`
- 存储:
  - 元数据: `SQLite`
  - 向量与稀疏检索: `Milvus`（dense + BM25/sparse）
  - 文件: `MinIO`（bucket=`rag_sth`）
- 模型与外部服务:
  - Layout parsing: `http://192.168.10.60:8888/layout-parsing`
  - Embedding: `bge-m3` (`http://192.168.10.60:5001/bge_embed`, dim=1024)
  - LLM: `deepseek-chat` (`https://api.deepseek.com/v1/chat/completions`, stream=true)
- 评估: `RAGAS`（faithfulness、answer_relevancy、context_precision、context_recall）

## 2) 核心参数（必须固定）
- 文档类型: 仅 `PDF`
- 文件大小上限: `100MB`
- 去重: `SHA256`
- 切分: semantic splitter，`chunk_size=2000`（中文字符），`overlap=50`
- 检索:
  - `topK=5`
  - 融合: 加权分数，向量:BM25=`0.7:0.3`
- 拒答:
  - 规则: `top1 向量相似度 < 0.1`
  - 文案: `无法回答`
  - 同时返回最近片段最多 `5` 条
- 引用格式: `[文件名-页码-段落ID]`
- 性能: 流式首字响应 `<=10s`
- 入库失败重试: `3` 次

## 3) 命名约定
- 通用:
  - 文件与目录: `snake_case`
  - Python 变量/函数: `snake_case`
  - Python 类: `PascalCase`
  - TS 变量/函数: `camelCase`
  - React 组件: `PascalCase`
  - 常量: `UPPER_SNAKE_CASE`
- API 路径:
  - 前缀统一: `/api/v1/...`
  - 资源名复数: `/files`, `/evaluations`
- 字段命名:
  - JSON API 使用 `snake_case`
  - 时间字段统一后缀 `_at`
  - 主键统一 `id`
- 状态枚举:
  - 任务状态仅允许: `QUEUED | RUNNING | SUCCESS | FAILED`

## 4) 文件结构（标准骨架）
```text
backend/
  app/
    api/v1/
    core/
    models/dto/
    models/entities/
    services/
    repositories/
    clients/
    workers/
    utils/
  config/
    base.yaml
    local.yaml
    prod.yaml
  scripts/
frontend/
  src/
    pages/
    components/
    services/
    stores/
    hooks/
    types/
    utils/
```

## 5) 组件模式
- 前端页面（MVP 必须）:
  - 文件上传页、文档列表页、解析预览页、聊天页、评估页、系统配置页
- 前端关键组件:
  - `FileUploadPanel`
  - `TaskStatusTag`
  - `ChunkPreviewTable`
  - `ChatStreamPanel`
  - `CitationList`
  - `MetricsCardGroup`
  - `TrendChart`
- 后端分层模式:
  - API 层只做参数校验与响应封装
  - Service 层实现业务编排
  - Repository 层负责 SQLite/Milvus/MinIO 读写
  - Client 层负责外部 API 调用
  - Worker 层负责异步任务执行与重试

## 6) 禁止操作（硬约束）
- 禁止在代码、配置仓库、日志中明文写入任何密钥/API Token
- 禁止绕过配置中心读取硬编码 endpoint/model 参数
- 禁止本期实现范围外功能:
  - 登录/权限
  - 多租户
  - 文档版本管理
  - reranker
  - 图片视觉理解（VLM）
  - 公式专门解析
- 禁止把页眉页脚内容写入可检索语料
- 禁止拆断句子进行 chunk 切分
- 禁止非流式问答输出（MVP 必须 stream）
- 禁止回答无引用（回答必须可追溯）
- 禁止在无法回答场景下“强行生成答案”
- 禁止偏离截止日目标，新增需求必须先冻结到二期

## 7) 完成定义（DoD）
- 满足 PRD MVP 验收项:
  - 上传->解析->切分->入库全链路可运行
  - 问答流式首字 <=10s（典型查询）
  - 引用格式正确且可回溯
  - RAGAS 四指标可计算并展示趋势
  - 交付: 可运行系统 + 操作文档 + 评估报告

