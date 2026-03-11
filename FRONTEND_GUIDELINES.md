# FRONTEND GUIDELINES

## 1. 页面范围（MVP）
- 必须页面：
1. `/studio`
2. `/gallery`
3. `/metrics`
- 本期不做登录页。

## 2. 路由与职责

### `/studio` 生成工作室
- 功能：
1. 选择新品图（来自新品库）
2. 展示检索 Top3 参考图
3. 展示 Qwen 产出的 `style_prompt`（可编辑）
4. 选择生成比例（1:1 / 3:4 / 4:1 / 9:16）
5. 触发生成
6. 实时展示任务状态（SSE）
7. 展示最终生成图或错误

### `/gallery` 历史画廊
- 功能：
1. 历史任务列表
2. 卡片展示原图、参考图、生成图
3. 查看 prompt、模型信息、状态
4. 下载原图/结果图（MinIO presigned URL）
5. 点赞/点踩反馈

### `/metrics` 指标页
- 指标固定三项：
1. 总任务数
2. 成功率
3. 点踩率
- 统计窗口：最近 30 天

## 3. 组件规范

## 3.1 命名规范
- 页面组件：`XxxPage.tsx`
- 业务组件：`XxxPanel.tsx`、`XxxCard.tsx`
- Hooks：`useXxx.ts`
- API 调用：`src/api/*.ts`
- 类型定义：`src/types/*.ts`

### 3.2 Studio 最小组件
1. `NewProductSelector`
2. `ReferenceTop3Panel`
3. `PromptEditor`
4. `GenerateControlPanel`
5. `GenerationPreview`
6. `SSEStatusTimeline`

### 3.3 Gallery 最小组件
1. `HistoryFilterBar`
2. `HistoryCardGrid`
3. `HistoryCard`
4. `FeedbackDialog`

## 4. 状态与交互

### 4.1 SSE 事件枚举（必须完整）
- `queued`
- `retrieving`
- `analyzing`
- `generating`
- `uploading`
- `done`
- `failed`

### 4.2 生成按钮状态
- `idle`：可点击
- `running`：禁用
- `error`：显示错误说明并允许重试
- `done`：显示结果图与下载操作

### 4.3 告警阻断行为
- 若命中相似度阈值（>=0.7）：
1. 在 UI 显示错误提示（阻断型）
2. 不展示“强制继续”入口
3. 允许用户修改 prompt 后重试新任务

## 5. 反馈规则
- 点赞：可选填写备注
- 点踩：
1. 文本必填
2. 最少 10 字
- 允许修改反馈（点赞/点踩可相互切换）

## 6. 会话规则
- 无登录场景使用 `session_id`（浏览器本地存储）区分会话。
- SSE 断线后不做事件续传，前端重连后主动拉取任务最新状态。

## 7. 视觉与可用性
- 生成页优先保证“一步到位看结果”：
1. 左：新品图
2. 中：Top3 参考图
3. 右：Prompt 与参数
4. 下：结果与状态
- 所有错误必须可读，不允许仅显示 `Internal Error`。
