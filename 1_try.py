# 相关链接：
# https://docs.langchain.com/oss/python/deepagents/quickstart
# langsmith可以查看 直接python直接即
# langgraph dev也可以观察

import os
from typing import Literal

from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model


def load_local_env(path: str = ".env") -> None:
    """Load .env without extra dependency; support `KEY = value`."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_local_env()

os.environ.setdefault("OPENAI_API_KEY", os.getenv("DEEPSEEK_API_KEY") or os.getenv("api_key", ""))
os.environ.setdefault("OPENAI_BASE_URL", os.getenv("DEEPSEEK_BASE_URL") or os.getenv("api_url", ""))

if os.getenv("LANGSMITH_API_KEY"):
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "deepagents")

if not os.getenv("OPENAI_API_KEY") or not os.getenv("OPENAI_BASE_URL") or not os.getenv("TAVILY_API_KEY"):
    raise RuntimeError(
        "Missing env vars. Please set `TAVILY_API_KEY`, and DeepSeek credentials "
        "(`api_key`/`api_url` or `DEEPSEEK_API_KEY`/`DEEPSEEK_BASE_URL`)."
    )

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

# System prompt to steer the agent to be an expert researcher
research_instructions = """

你是一名专业的研究分析专家，你的任务是针对用户提出的问题进行深入研究，并最终生成一份结构化、内容完整、逻辑清晰的研究报告。

你可以使用互联网搜索工具获取信息，这是你获取资料的主要方式。

## `internet_search`

使用该工具可以针对指定问题进行互联网搜索。

在使用该工具时，你可以：
- 指定搜索的查询语句（query）
- 指定返回结果的最大数量（max_results）
- 指定搜索主题（topic）
- 指定是否返回网页原始内容（raw_content）

## 工作流程

在回答用户问题时，请遵循以下步骤：

1. 理解用户的问题或研究主题。
2. 使用 `internet_search` 工具搜索相关资料。
3. 阅读并分析搜索结果中的关键信息。
4. 必要时进行多轮搜索，以获取更全面的信息。
5. 对获取到的信息进行整理和总结。
6. 最终生成一份完整的研究报告。

## 报告要求

最终输出应为一份结构清晰的研究报告，通常包括，中文生成最后结果：

- 背景介绍
- 现状分析
- 关键事实或数据
- 主要观点或结论
- 未来趋势（如果适用）

报告内容需要：

- 逻辑清晰
- 信息准确
- 表达专业
- 内容完整
"""

chat_model = init_chat_model(
    "openai:deepseek-chat",
    use_responses_api=False,  # DeepSeek uses chat completions API.
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
)

agent = create_deep_agent(
    model=chat_model,
    tools=[internet_search],
    system_prompt=research_instructions,
)

result = agent.invoke({"messages": [{"role": "user", "content": "如何学习ai infra相关技术?"}]})
print(result["messages"][-1].content)
