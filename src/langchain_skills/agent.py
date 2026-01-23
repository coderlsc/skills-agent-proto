"""
LangChain Skills Agent 主体

使用 LangChain 1.0 的 create_agent API 实现 Skills Agent，演示三层加载机制：
- Level 1: 启动时将 Skills 元数据注入 system_prompt
- Level 2: load_skill tool 加载详细指令
- Level 3: bash tool 执行脚本

与 claude-agent-sdk 实现的对比：
- claude-agent-sdk: setting_sources=["user", "project"] 自动处理
- LangChain 实现: 显式调用 SkillLoader，过程透明可见

流式输出支持：
- 支持 Extended Thinking 显示模型思考过程
- 事件级流式输出 (thinking / text / tool_call / tool_result)
"""

import os
from pathlib import Path
from typing import Optional, Iterator

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AIMessageChunk
from langgraph.checkpoint.memory import InMemorySaver

from .skill_loader import SkillLoader
from .tools import ALL_TOOLS, SkillAgentContext


# 加载环境变量
load_dotenv()


# 默认配置
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 16000
DEFAULT_TEMPERATURE = 1.0  # Extended Thinking 要求温度为 1.0
DEFAULT_THINKING_BUDGET = 10000


def get_anthropic_credentials() -> tuple[str | None, str | None]:
    """
    获取 Anthropic API 认证信息

    支持多种认证方式：
    1. ANTHROPIC_API_KEY - 标准 API Key
    2. ANTHROPIC_AUTH_TOKEN - 第三方代理认证 Token

    Returns:
        (api_key, base_url) 元组
    """
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    return api_key, base_url


def check_api_credentials() -> bool:
    """检查是否配置了 API 认证"""
    api_key, _ = get_anthropic_credentials()
    return api_key is not None


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
        enable_thinking: bool = True,
        thinking_budget: int = DEFAULT_THINKING_BUDGET,
    ):
        """
        初始化 Agent

        Args:
            model: 模型名称，默认 claude-sonnet-4-5-20250929
            skill_paths: Skills 搜索路径
            working_directory: 工作目录
            max_tokens: 最大 tokens
            temperature: 温度参数 (启用 thinking 时强制为 1.0)
            enable_thinking: 是否启用 Extended Thinking
            thinking_budget: thinking 的 token 预算
        """
        # thinking 配置
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget

        # 配置 (启用 thinking 时温度必须为 1.0)
        self.model_name = model or os.getenv("CLAUDE_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens or int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        if enable_thinking:
            self.temperature = 1.0  # Anthropic 要求启用 thinking 时温度为 1.0
        else:
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

        Extended Thinking 支持:
        - 启用后可获取模型的思考过程
        - 温度必须为 1.0

        认证支持:
        - 支持 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN
        - 支持 ANTHROPIC_BASE_URL 第三方代理
        """
        # 获取认证信息
        api_key, base_url = get_anthropic_credentials()

        # 构建初始化参数
        init_kwargs = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # 添加认证参数（支持第三方代理）
        if api_key:
            init_kwargs["api_key"] = api_key
        if base_url:
            init_kwargs["base_url"] = base_url

        # Extended Thinking 配置（直接传递，避免 model_kwargs 警告）
        if self.enable_thinking:
            init_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }

        # 初始化模型
        model = init_chat_model(
            self.model_name,
            **init_kwargs,
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
        流式调用 Agent (state 级别)

        Args:
            message: 用户消息
            thread_id: 会话 ID

        Yields:
            流式响应块 (完整状态更新)
        """
        config = {"configurable": {"thread_id": thread_id}}

        for chunk in self.agent.stream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            context=self.context,
            stream_mode="values",
        ):
            yield chunk

    def stream_events(self, message: str, thread_id: str = "default") -> Iterator[dict]:
        """
        事件级流式输出，支持 thinking 和 token 级流式

        Args:
            message: 用户消息
            thread_id: 会话 ID

        Yields:
            事件字典，格式如下:
            - {"type": "thinking", "content": "..."} - 思考内容片段
            - {"type": "text", "content": "..."} - 响应文本片段
            - {"type": "tool_call", "name": "...", "args": {...}} - 工具调用
            - {"type": "tool_result", "name": "...", "content": "..."} - 工具结果
            - {"type": "done", "response": "..."} - 完成标记，包含完整响应
        """
        config = {"configurable": {"thread_id": thread_id}}

        full_response = ""
        current_thinking = ""
        seen_tool_calls = set()  # 跟踪已发送的 tool_call

        # 使用 messages 模式获取 token 级流式
        for event in self.agent.stream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            context=self.context,
            stream_mode="messages",
        ):
            # event 是一个 tuple: (message_chunk, metadata)
            if not isinstance(event, tuple) or len(event) < 2:
                continue

            chunk, _ = event  # metadata 暂不使用

            # 处理 AIMessageChunk
            if isinstance(chunk, AIMessageChunk):
                content = chunk.content

                # content 可能是字符串或列表
                if isinstance(content, str) and content:
                    full_response += content
                    yield {"type": "text", "content": content}

                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get("type")

                            # thinking 块
                            if block_type == "thinking":
                                thinking_text = block.get("thinking", "")
                                if thinking_text:
                                    current_thinking += thinking_text
                                    yield {"type": "thinking", "content": thinking_text}

                            # text 块
                            elif block_type == "text":
                                text = block.get("text", "")
                                if text:
                                    full_response += text
                                    yield {"type": "text", "content": text}

                            # tool_use 块
                            elif block_type == "tool_use":
                                tool_id = block.get("id", "")
                                tool_name = block.get("name", "")
                                tool_args = block.get("input", {})
                                # 避免重复发送相同的 tool_call
                                if tool_id and tool_id not in seen_tool_calls:
                                    seen_tool_calls.add(tool_id)
                                    yield {
                                        "type": "tool_call",
                                        "id": tool_id,
                                        "name": tool_name,
                                        "args": tool_args,
                                    }

                # 处理 tool_calls (有些情况下在 chunk.tool_calls 中)
                if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    for tool_call in chunk.tool_calls:
                        tool_id = tool_call.get("id", "")
                        if tool_id and tool_id not in seen_tool_calls:
                            seen_tool_calls.add(tool_id)
                            yield {
                                "type": "tool_call",
                                "id": tool_id,
                                "name": tool_call.get("name", ""),
                                "args": tool_call.get("args", {}),
                            }

            # 处理 ToolMessage (工具执行结果)
            elif hasattr(chunk, "type") and chunk.type == "tool":
                tool_name = getattr(chunk, "name", "unknown")
                tool_content = getattr(chunk, "content", "")
                # 截断过长的结果用于显示
                display_content = str(tool_content)[:500]
                if len(str(tool_content)) > 500:
                    display_content += "..."
                yield {
                    "type": "tool_result",
                    "name": tool_name,
                    "content": display_content,
                }

        # 发送完成事件
        yield {"type": "done", "response": full_response}

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
    enable_thinking: bool = True,
    thinking_budget: int = DEFAULT_THINKING_BUDGET,
) -> LangChainSkillsAgent:
    """
    便捷函数：创建 Skills Agent

    Args:
        model: 模型名称
        skill_paths: Skills 搜索路径
        working_directory: 工作目录
        enable_thinking: 是否启用 Extended Thinking
        thinking_budget: thinking 的 token 预算

    Returns:
        配置好的 LangChainSkillsAgent 实例
    """
    return LangChainSkillsAgent(
        model=model,
        skill_paths=skill_paths,
        working_directory=working_directory,
        enable_thinking=enable_thinking,
        thinking_budget=thinking_budget,
    )
