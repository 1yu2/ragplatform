"""
可以帮我找一个复杂的关于deep agents项目来学习吗


• Searched LangChain deepagents GitHub examples complex project

• Searched https://github.com/langchain-ai/deepagents

• Searched https://github.com/langchain-ai/deepagents/blob/main/examples

• Searched https://github.com/langchain-ai/deepagents/blob/main/examples/deep_research

• Searched https://github.com/langchain-ai/deepagents/blob/main/examples/deep_research/agent.py

• Searched https://github.com/langchain-ai/deepagents/tree/main/examples/deep_research/research_agent

• Ran echo test
  └ test

• Searched

• Searched

• Searched

• Searched github langchain-ai deepagents examples/deep_research src/research_agent/agent.py

• Searched https://github.com/langchain-ai/open_deep_research

• Searched https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/configuration.py

• Searched https://github.com/langchain-ai/open_deep_research/raw/refs/heads/main/src/open_deep_research/configuration.py

• Searched https://github.com/langchain-ai/deepagents/tree/main/examples/deep_research

• Searched https://github.com/langchain-ai/deepagents/blob/main/examples/deep_research/agent.py

• Searched https://github.com/langchain-ai/deepagents/blob/main/examples/deep_research/research_agent/prompts.py

• Searched docs.langchain.com deepagents quickstart create_deep_agent

• Searched deepagents quickstart docs langchain

─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• 推荐你学这个官方复杂项目：deepagents/examples/deep_research
  链接：https://github.com/langchain-ai/deepagents/tree/main/examples/deep_research

  它适合“进阶学习”的原因：

  1. 有主代理 + 子代理协作（subagents），不是单一 agent。
  2. 有完整研究工作流提示词分层（workflow/delegation/researcher）。
  3. 有自定义工具链（tavily_search + think_tool）和多轮反思机制。
  4. 可直接用 langgraph dev + LangSmith Studio 观察执行链路。

  建议学习顺序：

  1. 先跑起来看行为：README.md
  2. 看总装配：agent.py
  3. 看策略设计：research_agent/prompts.py
  4. 看工具实现：research_agent/tools.py

  最短运行命令（在该目录）：

  uv sync
  langgraph dev

  你现在在用 DeepSeek，这个项目默认示例是 Anthropic/Gemini；README 写了可以传任意 LangChain model object，我的判断是可改成 openai:deepseek-chat 来跑。

  参考来源：

  - deep_research 示例目录与 README：https://github.com/langchain-ai/deepagents/tree/main/examples/deep_research
  - agent.py（主代理+子代理结构）：https://github.com/langchain-ai/deepagents/blob/main/examples/deep_research/agent.py
  - Deep Agents Python 概览（核心能力）：https://docs.langchain.com/oss/python/deepagents/overview


› Run /review on my current changes



"""