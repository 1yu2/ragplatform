# 内容构建智能体

<img width="1255" height="756" alt="content-cover-image" src="https://github.com/user-attachments/assets/4ebe0aba-2780-4644-8a00-ed4b96680dc9" />

一个用于撰写博客文章、LinkedIn 帖子和推文的智能体，包含封面图片。

**本示例演示了如何通过三个文件系统原语定义智能体：**
- **Memory**（`AGENTS.md`）- 持久化上下文，如品牌风格和写作规范
- **Skills**（`skills/*/SKILL.md`）- 特定任务的工作流，按需加载
- **Subagents**（`subagents.yaml`）- 专业子智能体，用于委托研究等任务

`content_writer.py` 脚本展示了如何将这些组合成一个可工作的智能体。

## 快速开始

```bash
# 设置 API 密钥
export ANTHROPIC_API_KEY="..."
export GOOGLE_API_KEY="..."      # 用于图片生成
export TAVILY_API_KEY="..."      # 用于网络搜索（可选）

# 运行（uv 首次运行时会自动安装依赖）
cd examples/content-builder-agent
uv run python content_writer.py "Write a blog post about prompt engineering"
```

**更多示例：**
```bash
uv run python content_writer.py "Create a LinkedIn post about AI agents"
uv run python content_writer.py "Write a Twitter thread about the future of coding"
```

## 工作原理

智能体通过磁盘上的文件配置，而非代码：

```
content-builder-agent/
├── AGENTS.md                    # 品牌风格和写作规范
├── subagents.yaml               # 子智能体定义
├── skills/
│   ├── blog-post/
│   │   └── SKILL.md             # 博客写作工作流
│   └── social-media/
│       └── SKILL.md             # 社交媒体工作流
└── content_writer.py            # 整合所有组件（包含工具）
```

| 文件 | 用途 | 加载时机 |
|------|------|----------|
| `AGENTS.md` | 品牌风格、语气、写作标准 | 始终加载（系统提示） |
| `subagents.yaml` | 研究和其他委托任务 | 始终加载（定义 `task` 工具） |
| `skills/*/SKILL.md` | 内容特定工作流 | 按需加载 |

**技能中有什么？** 每个技能教给智能体一个特定的工作流：
- **博客文章：** 结构（开篇 → 背景 → 主要内容 → 行动号召）、SEO 最佳实践、研究优先方法
- **社交媒体：** 平台特定格式（LinkedIn 字符限制、Twitter 线程结构）、话题标签使用
- **图片生成：** 针对不同内容类型（技术帖子、公告、思想领导力）的详细提示词工程指南

## 架构

```python
agent = create_deep_agent(
    memory=["./AGENTS.md"],                        # ← 中间件加载到系统提示
    skills=["./skills/"],                          # ← 中间件按需加载
    tools=[generate_cover, generate_social_image], # ← 图片生成工具
    subagents=load_subagents("./subagents.yaml"), # ← 见下方说明
    backend=FilesystemBackend(root_dir="./"),
)
```

`memory` 和 `skills` 参数由 deepagents 中间件本地处理。工具在脚本中定义并直接传递。

**关于子智能体的说明：** 与 `memory` 和 `skills` 不同，子智能体必须在代码中定义。我们使用一个小的 `load_subagents()` 助手将配置外部化到 YAML。你也可以内联定义：

```python
subagents=[
    {
        "name": "researcher",
        "description": "Research topics before writing...",
        "model": "anthropic:claude-haiku-4-5-20251001",
        "system_prompt": "You are a research assistant...",
        "tools": [web_search],
    }
],
```

**流程：**
1. 智能体接收任务 → 加载相关技能（blog-post 或 social-media）
2. 将研究委托给 `researcher` 子智能体 → 保存到 `research/`
3. 按照技能工作流撰写内容 → 保存到 `blogs/` 或 `linkedin/`
4. 使用 Gemini 生成封面图片 → 与内容一起保存

## 输出

```
blogs/
└── prompt-engineering/
    ├── post.md       # 博客内容
    └── hero.png      # 生成的封面图片

linkedin/
└── ai-agents/
    ├── post.md       # 帖子内容
    └── image.png      # 生成的图片

research/
└── prompt-engineering.md   # 研究笔记
```

## 自定义

**改变语气：** 编辑 `AGENTS.md` 修改品牌风格。

**添加内容类型：** 创建 `skills/<name>/SKILL.md`，包含 YAML 前言：
```yaml
---
name: newsletter
description: Use this skill when writing email newsletters
---
# Newsletter Skill
...
```

**添加子智能体：** 添加到 `subagents.yaml`：
```yaml
editor:
  description: Review and improve drafted content
  model: anthropic:claude-haiku-4-5-20251001
  system_prompt: |
    You are an editor. Review the content and suggest improvements...
  tools: []
```

**添加工具：** 在 `content_writer.py` 中使用 `@tool` 装饰器定义，并添加到 `tools=[]`。

## 安全说明

此智能体具有文件系统访问权限，可以读取、写入和删除你机器上的文件。在发布之前请审查生成的内容，并避免在包含敏感数据的目录中运行。

## 依赖要求

- Python 3.11+
- `ANTHROPIC_API_KEY` - 用于主智能体
- `GOOGLE_API_KEY` - 用于图片生成（使用 Gemini 的 [Imagen / "nano banana"](https://ai.google.dev/gemini-api/docs/image-generation)，通过 `gemini-2.5-flash-image`）
- `TAVILY_API_KEY` - 用于网络搜索（可选，没有它研究仍然可以工作）






Content Builder Agent 架构解析

```yaml
  ┌─────────────────────────────────────────────────────────────────┐
  │                        主 Agent                                  │
  │                    (create_deep_agent)                           │
  ├─────────────────────────────────────────────────────────────────┤
  │  memory (AGENTS.md)     ← 品牌风格、写作规范（始终加载）         │
  │  skills (skills/)       ← 技能工作流（按需加载）                 │
  │  tools (generate_cover) ← 图片生成工具                           │
  │  subagents (researcher) ← 子智能体（委托研究）                   │
  └─────────────────────────────────────────────────────────────────┘
```
  ---
  1. AGENTS.md - 智能体身份和规范

  作用：定义 Agent 的"身份"和"行为准则"，类似于系统提示词。

  包含：
  - 品牌风格 - 专业但平易近人、清晰直接
  - 写作标准 - 主动语态、以价值开篇
  - 内容支柱 - AI、开发者工具、架构等
  - 研究要求 - 必须先研究再写作

  # 内容写作智能体
  你是一家科技公司的内容创作者...
  ## 品牌风格
  - 专业但平易近人
  - 清晰直接

  ---
  2. Skills - 技能工作流

  作用：定义特定任务的"专业工作流"，按需加载（渐进式披露）。
```yaml
  skills/
  ├── blog-post/
  │   └── SKILL.md      # 博客写作流程
  └── social-media/
      └── SKILL.md      # 社交媒体写作流程
```

  何时使用：
  - 当用户说"写博客" → 自动加载 blog-post/SKILL.md
  - 当用户说"写 LinkedIn" → 自动加载 social-media/SKILL.md

  每个 SKILL.md 包含：
  - 何时使用这个技能
  - 具体工作流程
  - 输出格式要求

  ---
  3. Tools - 工具

  作用：Agent 可以调用的具体功能函数。
```python
  @tool
  def generate_cover(prompt: str, slug: str) -> str:
      """生成博客封面图片"""
      ...

  @tool
  def generate_social_image(prompt: str, platform: str, slug: str) -> str:
      """生成社交媒体图片"""
      ...

  @tool
  def web_search(query: str, max_results: int = 5) -> dict:
      """网络搜索"""
```
  ---
  4. Subagents - 子智能体

  作用：将复杂任务委托给专业的小 Agent。
```yaml

  主 Agent
     │
     ├── 研究任务 ──► researcher 子代理 (web_search 工具)
     │
     ├── 写博客    ──► blog-post 技能
     │
     └── 生成图片  ──► generate_cover 工具
```
  ---
  完整流程示例

  用户输入: "写一篇关于 AI agents 的博客"

  1. 加载 AGENTS.md
     → 知道要用专业但平易近人的语气

  2. 识别需要 blog-post 技能
     → 加载 skills/blog-post/SKILL.md
     → 知道要先研究再写作

  3. 委托 researcher 子代理研究
     → 使用 web_search 工具
     → 保存研究结果到 research/ai-agents.md

  4. 按照 SKILL.md 结构写博客
     → 开篇 → 背景 → 主要内容 → 结论

  5. 生成封面图片
     → 使用 generate_cover 工具
     → 保存到 blogs/ai-agents/hero.png

  6. 保存文章
     → blogs/ai-agents/post.md

  ---
  总结

  | 组件        | 作用           | 加载时机 |
  |-----------|--------------|------|
  | AGENTS.md | 身份、风格、规范     | 始终加载 |
  | Skills    | 特定任务的工作流     | 按需加载 |
  | Tools     | 可调用的函数       | 始终可用 |
  | Subagents | 委托的专业小 Agent | 按需调用 |


 定义的所有工具是主agent和subagent都能调用吗

⏺ 不完全是。工具可以分配给不同的 Agent：
```python
  # content_writer.py 中的配置
  agent = create_deep_agent(
      memory=["./AGENTS.md"],
      skills=["./skills/"],
      tools=[generate_cover, generate_social_image],  # ← 主 Agent 的工具
      subagents=load_subagents(EXAMPLE_DIR / "subagents.yaml"),  # ← 子代理定义
  )
```
  ---
  工具分配规则


  | 工具                    | 谁可以用                 |
  |-----------------------|----------------------|
  | generate_cover        | 主 Agent              |
  | generate_social_image | 主 Agent              |
  | web_search            | 子 Agent (researcher) |

  ---
  subagents.yaml 中定义了子 Agent 的工具
```yaml
  researcher:
    description: ...
    model: openai:MiniMax/MiniMax-M2.5
    tools:
      - web_search    # ← 只有 researcher 能用
```
  ---
  工作原理
```yaml
  主 Agent
     │
     ├── 生成图片 → generate_cover ✓
     │
     └── 委托研究 → researcher (subagent)
                       │
                       └── web_search ✓
                       ✗ generate_cover (没有权限)
```

  主 Agent 不能 调用 web_search（除非也加到主 Agent 的 tools 列表中）

  子 Agent 不能 调用 generate_cover（除非在 subagents.yaml 中添加）

  ---
  如果想让子 Agent 也能调用主 Agent 的工具

  需要在 subagents.yaml 的 tools 中添加：
```yaml
  researcher:
    ...
    tools:
      - web_search
      - generate_cover   # 添加这个
```