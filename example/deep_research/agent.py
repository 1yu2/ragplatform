"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.
"""

from datetime import datetime
import os

from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent

from research_agent.prompt import (
    RESEARCHER_INSTRUCTIONS,
    RESEARCH_WORKFLOW_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)
from research_agent.tools import tavily_search, think_tool, write_file

# Limits
max_concurrent_research_units = 3
max_researcher_iterations = 3

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")

# Combine orchestrator instructions (RESEARCHER_INSTRUCTIONS only for sub-agents)
INSTRUCTIONS = (
    RESEARCH_WORKFLOW_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
        max_concurrent_research_units=max_concurrent_research_units,
        max_researcher_iterations=max_researcher_iterations,
    )
)

# Create research sub-agent
research_sub_agent = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
    "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
    "tools": [tavily_search, think_tool, write_file],
}

chat_model = init_chat_model(
    "openai:MiniMax/MiniMax-M2.5",
    use_responses_api=False,  # DeepSeek uses chat completions API.
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
)

# Create the agent
agent = create_deep_agent(
    model=chat_model,
    tools=[tavily_search, think_tool, write_file],
    system_prompt=INSTRUCTIONS,
    subagents=[research_sub_agent],
)
"""
输入：
{
  "messages": [
    {
      "role": "user",
      "content": "目前市面上最成功multiagent的开源项目"
    }
  ]
}
调试：
langgraph dev
"""