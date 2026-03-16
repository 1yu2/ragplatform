# Deep Research Agent 架构详解

## 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Deep Researcher (主图)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌──────────────────────┐    ┌──────────────────┐  │
│  │clarify_with_user│───▶│ write_research_brief │───▶│ supervisor_subgraph│  │
│  └─────────────────┘    └──────────────────────┘    └────────┬─────────┘  │
│                                                              │             │
│                                                              ↓             │
│                                                    ┌─────────────────────┐ │
│                                                    │ final_report_generation│
│                                                    └──────────┬──────────┘ │
│                                                               │             │
│                                                               ↓             │
│                                                           END (返回用户)    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    Supervisor 子图（研究管理）                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  START ──▶ supervisor ──▶ supervisor_tools ──▶ (循环) ──▶ END            │
│              ↓                                                              │
│         调用模型决策                                                        │
│              ↓                                                              │
│         工具：ConductResearch / think_tool / ResearchComplete              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    Researcher 子图（执行研究）                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  START ──▶ researcher ──▶ researcher_tools ──▶ (循环) ──▶ compress ──▶ END
│              ↓                                                             │
│         调用模型决策                                                        │
│              ↓                                                             │
│         工具：搜索 / think_tool / ResearchComplete                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 每个节点详解

### 1. clarify_with_user（用户澄清）

**作用**：分析用户消息，判断是否需要澄清问题

```python
# deep_researcher.py:60
async def clarify_with_user(state, config):
    # 检查配置是否允许澄清
    # 调用模型判断是否需要澄清
    # 返回：继续研究 OR 结束并询问用户
```

**决策**：
- 需要澄清 → 结束，返回澄清问题
- 不需要澄清 → 继续

---

### 2. write_research_brief（编写研究简报）

**作用**：将用户消息转换为结构化的研究主题

```python
# deep_researcher.py:121
async def write_research_brief(state, config):
    # 调用模型分析用户问题
    # 生成 research_brief（研究主题）
    # 初始化 supervisor 的系统提示
```

**输出**：
- `research_brief`: 研究主题描述
- `supervisor_messages`: 初始化 supervisor 的消息

---

### 3. supervisor_subgraph（Supervisor 子图）

**作用**：管理整个研究过程，决定研究方向和策略

```
┌──────────────────────────────────────────────────┐
│           Supervisor 工作流程                     │
├──────────────────────────────────────────────────┤
│                                                  │
│  supervisor ──▶ supervisor_tools                │
│       ↑                    │                     │
│       │                    ↓                     │
│       │            ┌───────────────┐             │
│       │            │ 处理工具调用   │             │
│       │            └───────┬───────┘             │
│       │                    │                     │
│       │                    ↓                     │
│       │            ┌───────────────┐             │
│       └────────────│ 判断退出条件   │             │
│                  └───────┬───────┘             │
│                          │                     │
│                          ↓                     │
│                    END 或 继续                   │
└──────────────────────────────────────────────────┘
```

---

### 4. supervisor（Supervisor 决策）

**作用**：模型思考下一步该做什么

```python
# deep_researcher.py:183
async def supervisor(state, config):
    # 可用工具：ConductResearch, ResearchComplete, think_tool
    response = await research_model.ainvoke(supervisor_messages)
    # 模型决定调用哪个工具
```

**可用工具**：

| 工具 | 作用 | 说明 |
|------|------|------|
| **ConductResearch** | 委托子研究员 | 将任务分发给 Researcher |
| **ResearchComplete** | 标记完成 | 告诉 Supervisor 可以结束研究了 |
| **think_tool** | 战略反思 | 让模型暂停思考 |

---

### 5. supervisor_tools（执行 Supervisor 工具）

**作用**：执行 Supervisor 调用的工具

```python
# deep_researcher.py:230
async def supervisor_tools(state, config):
    # 检查退出条件
    # 处理 think_tool 调用
    # 处理 ConductResearch 调用（并行执行多个 Researcher）
```

**退出条件**（满足任一即结束）：
1. 达到最大迭代次数
2. 没有工具调用
3. 调用了 ResearchComplete

---

### 6. ConductResearch（委托研究）

**作用**：定义一个研究任务，包含具体的研究主题

```python
# state.py:15
class ConductResearch(BaseModel):
    research_topic: str = Field(
        description="The topic to research. Should be a single topic..."
    )
```

**使用示例**：
```
Supervisor 调用 ConductResearch(research_topic="研究 OpenClaw 的技术架构")
    ↓
创建 Researcher 子图执行研究
    ↓
返回压缩后的研究结果
```

---

### 7. Researcher（研究员）

**作用**：执行具体的研究任务

```python
# deep_researcher.py:370
async def researcher(state, config):
    # 可用工具：搜索工具 + think_tool + ResearchComplete
    # 执行搜索和思考
```

**可用工具**：

| 工具 | 作用 |
|------|------|
| **tavily_search** | Tavily 搜索 |
| **web_search** | 原生搜索（Anthropic/OpenAI） |
| **think_tool** | 反思和规划 |
| **ResearchComplete** | 标记完成 |

---

### 8. researcher_tools（执行 Researcher 工具）

**作用**：执行 Researcher 调用的搜索工具

```python
# deep_researcher.py:440
async def researcher_tools(state, config):
    # 执行搜索工具
    # 检查退出条件
```

**退出条件**：
1. 达到最大工具调用次数
2. 调用了 ResearchComplete

---

### 9. compress_research（压缩研究结果）

**作用**：将大量搜索结果压缩成简洁摘要

```python
# deep_researcher.py:516
async def compress_research(state, config):
    # 获取所有搜索结果
    # 调用 LLM 压缩
    # 返回压缩后的摘要
```

**输出**：
- `compressed_research`: 压缩后的摘要
- `raw_notes`: 原始笔记

---

### 10. final_report_generation（生成最终报告）

**作用**：将所有研究结果整合成最终报告

```python
# deep_researcher.py:612
async def final_report_generation(state, config):
    # 获取所有 notes（Supervisor 收集的研究结果）
    # 调用 LLM 生成最终报告
    # 返回报告给用户
```

**注意**：这是**直接调用 LLM**，不是工具调用

---

## 工具汇总表

| 工具 | 定义位置 | 使用者 | 作用 |
|------|---------|--------|------|
| **think_tool** | `utils.py:245` | Supervisor, Researcher | 战略反思 |
| **ResearchComplete** | `state.py:21` | Supervisor, Researcher | 标记完成 |
| **ConductResearch** | `state.py:15` | Supervisor | 委托子研究 |
| **tavily_search** | `utils.py:43` | Researcher | 搜索网页 |
| **web_search** | 配置选择 | Researcher | 原生搜索 |

---

## 完整数据流示例

```
用户："研究 OpenClaw"

1. clarify_with_user
   → 不需要澄清，返回"好的，开始研究"

2. write_research_brief
   → 生成 research_brief: "研究 OpenClaw 项目..."

3. supervisor
   → 模型决定：ConductResearch("OpenClaw 概述")

4. supervisor_tools
   → 执行 ConductResearch，启动 Researcher

5. researcher
   → 模型决定：tavily_search(["OpenClaw AI"])

6. researcher_tools
   → 执行搜索，获取结果

7. researcher（循环直到完成）
   → 多次搜索、反思

8. compress_research
   → 压缩所有搜索结果为摘要

9. 返回结果给 Supervisor
   → Supervisor 收集所有子研究员结果

10. final_report_generation
    → 生成最终报告，返回给用户
```

---

## 文件位置

- 主图定义：`src/open_deep_research/deep_researcher.py`
- 状态定义：`src/open_deep_research/state.py`
- 工具定义：`src/open_deep_research/utils.py`
- 配置定义：`src/open_deep_research/configuration.py`
- 提示词定义：`src/open_deep_research/prompts.py`
