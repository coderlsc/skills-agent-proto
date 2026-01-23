"""
LangChain Skills Agent 主体

使用 LangChain 1.0 的 create_agent API 实现 Skills Agent，演示三层加载机制：
- Level 1: 启动时将 Skills 元数据注入 system_prompt
- Level 2: load_skill tool 加载详细指令
- Level 3: bash tool 执行脚本

与 claude-agent-sdk 实现的对比：
- claude-agent-sdk: setting_sources=["user", "project"] 自动处理
- LangChain 实现: 显式调用 SkillLoader，过程透明可见
"""

import os
from pathlib import Path
from typing import Optional, Iterator

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from .skill_loader import SkillLoader
from .tools import ALL_TOOLS, SkillAgentContext


# 加载环境变量
load_dotenv()


# 默认配置
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7


class LangChainSkillsAgent:
    """
    基于 LangChain 1.0 的 Skills Agent

    演示目的：展示 Skills 三层加载机制的底层原理

    使用示例：
        agent = LangChainSkillsAgent()

        # 查看 system prompt（展示 Level 1）
        print(agent.get_system_prompt())

        # 运行 agent
        for chunk in agent.stream("提取这篇公众号文章"):
            response = agent.get_last_response(chunk)
            if response:
                print(response)
    """

    def __init__(
        self,
        model: Optional[str] = None,
        skill_paths: Optional[list[Path]] = None,
        working_directory: Optional[Path] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """
        初始化 Agent

        Args:
            model: 模型名称，默认 claude-sonnet-4-5-20250929
            skill_paths: Skills 搜索路径
            working_directory: 工作目录
            max_tokens: 最大 tokens
            temperature: 温度参数
        """
        # 配置
        self.model_name = model or os.getenv("CLAUDE_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens or int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        self.temperature = temperature or float(os.getenv("MODEL_TEMPERATURE", str(DEFAULT_TEMPERATURE)))
        self.working_directory = working_directory or Path.cwd()

        # 初始化 SkillLoader
        self.skill_loader = SkillLoader(skill_paths)

        # Level 1: 构建 system prompt（将 Skills 元数据注入）
        self.system_prompt = self._build_system_prompt()

        # 创建上下文（供 tools 使用）
        self.context = SkillAgentContext(
            skill_loader=self.skill_loader,
            working_directory=self.working_directory,
        )

        # 创建 LangChain Agent
        self.agent = self._create_agent()

    def _build_system_prompt(self) -> str:
        """
        构建 system prompt

        这是 Level 1 的核心：将所有 Skills 的元数据注入到 system prompt。
        每个 skill 约 100 tokens，启动时一次性加载。
        """
        base_prompt = """You are a helpful coding assistant with access to specialized skills.

Your capabilities include:
- Loading and using specialized skills for specific tasks
- Executing bash commands and scripts
- Reading and writing files
- Following skill instructions to complete complex tasks

When a user request matches a skill's description, use the load_skill tool to get detailed instructions before proceeding."""

        return self.skill_loader.build_system_prompt(base_prompt)

    def _create_agent(self):
        """
        创建 LangChain Agent

        使用 LangChain 1.0 的 create_agent API:
        - model: 可以是字符串 ID 或 model 实例
        - tools: 工具列表
        - system_prompt: 系统提示（Level 1 注入 Skills 元数据）
        - context_schema: 上下文类型（供 ToolRuntime 使用）
        - checkpointer: 会话记忆
        """
        # 初始化模型
        model = init_chat_model(
            self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # 创建 Agent
        agent = create_agent(
            model=model,
            tools=ALL_TOOLS,
            system_prompt=self.system_prompt,
            context_schema=SkillAgentContext,
            checkpointer=InMemorySaver(),
        )

        return agent

    def get_system_prompt(self) -> str:
        """
        获取当前 system prompt

        用于演示和调试，展示 Level 1 注入的内容。
        """
        return self.system_prompt

    def get_discovered_skills(self) -> list[dict]:
        """
        获取发现的 Skills 列表

        用于演示 Level 1 的 Skills 发现过程。
        """
        skills = self.skill_loader.scan_skills()
        return [
            {
                "name": s.name,
                "description": s.description,
                "path": str(s.skill_path),
            }
            for s in skills
        ]

    def invoke(self, message: str, thread_id: str = "default") -> dict:
        """
        同步调用 Agent

        Args:
            message: 用户消息
            thread_id: 会话 ID（用于多轮对话）

        Returns:
            Agent 响应
        """
        config = {"configurable": {"thread_id": thread_id}}

        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            context=self.context,
        )

        return result

    def stream(self, message: str, thread_id: str = "default") -> Iterator[dict]:
        """
        流式调用 Agent

        Args:
            message: 用户消息
            thread_id: 会话 ID

        Yields:
            流式响应块
        """
        config = {"configurable": {"thread_id": thread_id}}

        for chunk in self.agent.stream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            context=self.context,
            stream_mode="values",
        ):
            yield chunk

    def get_last_response(self, result: dict) -> str:
        """
        从结果中提取最后的 AI 响应文本

        Args:
            result: invoke 或 stream 的结果

        Returns:
            AI 响应文本
        """
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                if isinstance(msg.content, str):
                    return msg.content
                elif isinstance(msg.content, list):
                    # 处理多部分内容
                    text_parts = []
                    for part in msg.content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                        elif isinstance(part, str):
                            text_parts.append(part)
                    return "\n".join(text_parts)
        return ""


def create_skills_agent(
    model: Optional[str] = None,
    skill_paths: Optional[list[Path]] = None,
    working_directory: Optional[Path] = None,
) -> LangChainSkillsAgent:
    """
    便捷函数：创建 Skills Agent

    Args:
        model: 模型名称
        skill_paths: Skills 搜索路径
        working_directory: 工作目录

    Returns:
        配置好的 LangChainSkillsAgent 实例
    """
    return LangChainSkillsAgent(
        model=model,
        skill_paths=skill_paths,
        working_directory=working_directory,
    )
