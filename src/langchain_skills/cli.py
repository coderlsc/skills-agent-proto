"""
LangChain Skills Agent CLI

命令行入口，提供演示和交互功能：
- 列出发现的 Skills
- 显示 system prompt（演示 Level 1）
- 执行用户请求（支持流式输出和 thinking 显示）
- 交互式对话模式

流式输出特性：
- 🧠 Thinking 面板：实时显示模型思考过程（蓝色）
- 🔧 Tool Calls：显示工具调用（黄色）
- 💬 Response 面板：逐字显示最终响应（绿色）
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console, Group
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.spinner import Spinner
from rich.layout import Layout
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .agent import LangChainSkillsAgent, check_api_credentials
from .skill_loader import SkillLoader


# 加载环境变量
load_dotenv()

console = Console()


def create_streaming_display(
    thinking_text: str = "",
    response_text: str = "",
    tool_calls: list = None,
    tool_results: list = None,
    is_thinking: bool = False,
    is_responding: bool = False,
    is_waiting: bool = False,
) -> Group:
    """
    创建流式显示的布局

    Args:
        thinking_text: 当前累积的 thinking 文本
        response_text: 当前累积的响应文本
        tool_calls: 工具调用列表
        tool_results: 工具结果列表
        is_thinking: 是否正在思考
        is_responding: 是否正在响应
        is_waiting: 是否处于初始等待状态

    Returns:
        Rich Group 对象
    """
    elements = []

    # 初始等待状态 - 显示 spinner 提示
    if is_waiting and not thinking_text and not response_text and not tool_calls:
        elements.append(Text("🤔 AI 正在思考中...", style="cyan"))
        return Group(*elements)

    # Thinking 面板
    if thinking_text:
        thinking_title = "🧠 Thinking"
        if is_thinking:
            thinking_title += " ..."
        # 限制显示长度，保留最新内容
        display_thinking = thinking_text
        if len(display_thinking) > 1000:
            display_thinking = "..." + display_thinking[-1000:]
        elements.append(Panel(
            Text(display_thinking, style="dim"),
            title=thinking_title,
            border_style="blue",
            padding=(0, 1),
        ))

    # Tool Calls 显示
    if tool_calls:
        for tc in tool_calls:
            tool_text = f"🔧 {tc['name']}"
            if tc.get("args"):
                # 简化显示参数
                args_str = str(tc["args"])
                if len(args_str) > 100:
                    args_str = args_str[:100] + "..."
                tool_text += f"\n   {args_str}"
            elements.append(Text(tool_text, style="yellow"))

    # Tool Results 显示
    if tool_results:
        for tr in tool_results:
            result_text = f"📤 {tr['name']} 结果:"
            content = tr.get("content", "")
            if len(content) > 200:
                content = content[:200] + "..."
            result_text += f"\n   {content}"
            elements.append(Text(result_text, style="cyan dim"))

    # Response 面板
    if response_text:
        response_title = "💬 Response"
        if is_responding:
            response_title += " ..."
        elements.append(Panel(
            Markdown(response_text),
            title=response_title,
            border_style="green",
            padding=(0, 1),
        ))
    elif is_responding and not thinking_text:
        # 显示等待指示器
        elements.append(Text("⏳ Generating response...", style="dim"))

    return Group(*elements) if elements else Text("⏳ Processing...", style="dim")


def print_banner():
    """打印欢迎横幅"""
    banner = """
[bold cyan]LangChain Skills Agent[/bold cyan]
[dim]演示 Skills 三层加载机制的底层原理[/dim]

[yellow]Level 1[/yellow]: 启动时 → Skills 元数据注入 system prompt
[yellow]Level 2[/yellow]: 请求匹配时 → load_skill 加载详细指令
[yellow]Level 3[/yellow]: 执行时 → bash 运行脚本，仅输出进入上下文
"""
    console.print(Panel(banner, title="Skills Agent Demo", border_style="cyan"))


def cmd_list_skills():
    """列出发现的 Skills"""
    console.print("\n[bold cyan]Discovering Skills...[/bold cyan]\n")

    loader = SkillLoader()
    skills = loader.scan_skills()

    if not skills:
        console.print("[yellow]No skills found.[/yellow]")
        console.print("Skills are loaded from:")
        console.print("  - ~/.claude/skills/")
        console.print("  - .claude/skills/")
        return

    table = Table(title=f"Found {len(skills)} Skills")
    table.add_column("Name", style="green")
    table.add_column("Description", style="white")
    table.add_column("Path", style="dim")

    for skill in skills:
        # 截断描述
        desc = skill.description
        if len(desc) > 60:
            desc = desc[:57] + "..."

        table.add_row(
            skill.name,
            desc,
            str(skill.skill_path.relative_to(skill.skill_path.parent.parent)),
        )

    console.print(table)


def cmd_show_prompt():
    """显示 system prompt（演示 Level 1）"""
    console.print("\n[bold cyan]Building System Prompt (Level 1)...[/bold cyan]\n")

    agent = LangChainSkillsAgent()
    prompt = agent.get_system_prompt()

    console.print(Panel(
        Markdown(prompt),
        title="System Prompt",
        subtitle="Skills metadata injected here",
        border_style="green",
    ))

    # 统计信息
    skills = agent.get_discovered_skills()
    token_estimate = len(prompt) // 4  # 粗略估算

    console.print(f"\n[dim]Skills discovered: {len(skills)}[/dim]")
    console.print(f"[dim]Estimated tokens: ~{token_estimate}[/dim]")


def cmd_run(prompt: str, enable_thinking: bool = True):
    """
    执行单次请求，支持流式输出和 thinking 显示

    Args:
        prompt: 用户请求
        enable_thinking: 是否启用 thinking 显示
    """
    console.print(Panel(f"[bold cyan]User Request:[/bold cyan]\n{prompt}"))
    console.print()

    # 检查 API 认证（支持 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN）
    if not check_api_credentials():
        console.print("[red]Error: API credentials not set[/red]")
        console.print("Please set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN in .env file")
        sys.exit(1)

    agent = LangChainSkillsAgent(enable_thinking=enable_thinking)

    console.print("[dim]Running agent with streaming output...[/dim]\n")

    try:
        # 流式状态
        thinking_text = ""
        response_text = ""
        tool_calls = []
        tool_results = []
        is_thinking = False
        is_responding = False

        with Live(console=console, refresh_per_second=10, transient=True) as live:
            # 立即显示等待状态
            live.update(create_streaming_display(is_waiting=True))

            for event in agent.stream_events(prompt):
                event_type = event.get("type")

                if event_type == "thinking":
                    is_thinking = True
                    is_responding = False
                    thinking_text += event.get("content", "")
                    live.update(create_streaming_display(
                        thinking_text=thinking_text,
                        response_text=response_text,
                        tool_calls=tool_calls,
                        tool_results=tool_results,
                        is_thinking=True,
                        is_responding=False,
                    ))

                elif event_type == "text":
                    is_thinking = False
                    is_responding = True
                    response_text += event.get("content", "")
                    live.update(create_streaming_display(
                        thinking_text=thinking_text,
                        response_text=response_text,
                        tool_calls=tool_calls,
                        tool_results=tool_results,
                        is_thinking=False,
                        is_responding=True,
                    ))

                elif event_type == "tool_call":
                    is_thinking = False
                    tool_calls.append({
                        "name": event.get("name", "unknown"),
                        "args": event.get("args", {}),
                    })
                    live.update(create_streaming_display(
                        thinking_text=thinking_text,
                        response_text=response_text,
                        tool_calls=tool_calls,
                        tool_results=tool_results,
                        is_thinking=False,
                        is_responding=False,
                    ))

                elif event_type == "tool_result":
                    tool_results.append({
                        "name": event.get("name", "unknown"),
                        "content": event.get("content", ""),
                    })
                    live.update(create_streaming_display(
                        thinking_text=thinking_text,
                        response_text=response_text,
                        tool_calls=tool_calls,
                        tool_results=tool_results,
                        is_thinking=False,
                        is_responding=False,
                    ))

                elif event_type == "done":
                    # 完成，获取最终响应
                    if not response_text:
                        response_text = event.get("response", "")

        # 显示最终结果
        console.print()

        # 显示 thinking（如果有）
        if thinking_text:
            # 只显示部分 thinking
            display_thinking = thinking_text
            if len(display_thinking) > 2000:
                display_thinking = display_thinking[:1000] + "\n\n... (truncated) ...\n\n" + display_thinking[-1000:]
            console.print(Panel(
                Text(display_thinking, style="dim"),
                title="🧠 Thinking",
                border_style="blue",
            ))

        # 显示工具调用和结果
        if tool_calls:
            for i, tc in enumerate(tool_calls):
                console.print(f"[yellow]🔧 Tool: {tc['name']}[/yellow]")
                if tc.get("args"):
                    args_str = str(tc["args"])
                    if len(args_str) > 200:
                        args_str = args_str[:200] + "..."
                    console.print(f"[dim]   Args: {args_str}[/dim]")
                # 显示对应的工具结果
                if i < len(tool_results):
                    tr = tool_results[i]
                    content = tr.get("content", "")
                    if len(content) > 500:
                        content = content[:500] + "..."
                    console.print(f"[cyan]📤 Result:[/cyan]")
                    console.print(f"[dim]   {content}[/dim]")
            console.print()

        # 显示最终响应
        if response_text:
            console.print(Panel(
                Markdown(response_text),
                title="💬 Response",
                border_style="green",
            ))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


def cmd_interactive(enable_thinking: bool = True):
    """
    交互式对话模式，支持流式输出和 thinking 显示

    Args:
        enable_thinking: 是否启用 thinking 显示
    """
    print_banner()

    # 检查 API 认证（支持 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN）
    if not check_api_credentials():
        console.print("[red]Error: API credentials not set[/red]")
        console.print("Please set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN in .env file")
        sys.exit(1)

    agent = LangChainSkillsAgent(enable_thinking=enable_thinking)

    # 显示发现的 Skills
    skills = agent.get_discovered_skills()
    console.print(f"\n[green]✓[/green] Discovered {len(skills)} skills")
    for skill in skills:
        console.print(f"  - {skill['name']}")
    console.print()

    thinking_status = "[green]enabled[/green]" if enable_thinking else "[dim]disabled[/dim]"
    console.print(f"[dim]Extended Thinking: {thinking_status}[/dim]")
    console.print("[dim]Commands: 'exit' to quit, 'skills' to list skills, 'prompt' to show system prompt[/dim]\n")

    thread_id = "interactive"

    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()

            if not user_input:
                continue

            # 特殊命令
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "skills":
                cmd_list_skills()
                continue

            if user_input.lower() == "prompt":
                cmd_show_prompt()
                continue

            # 运行 agent（流式输出）
            console.print()

            # 流式状态
            thinking_text = ""
            response_text = ""
            tool_calls = []
            tool_results = []

            with Live(console=console, refresh_per_second=10, transient=True) as live:
                # 立即显示等待状态
                live.update(create_streaming_display(is_waiting=True))

                for event in agent.stream_events(user_input, thread_id=thread_id):
                    event_type = event.get("type")

                    if event_type == "thinking":
                        thinking_text += event.get("content", "")
                        live.update(create_streaming_display(
                            thinking_text=thinking_text,
                            response_text=response_text,
                            tool_calls=tool_calls,
                            tool_results=tool_results,
                            is_thinking=True,
                            is_responding=False,
                        ))

                    elif event_type == "text":
                        response_text += event.get("content", "")
                        live.update(create_streaming_display(
                            thinking_text=thinking_text,
                            response_text=response_text,
                            tool_calls=tool_calls,
                            tool_results=tool_results,
                            is_thinking=False,
                            is_responding=True,
                        ))

                    elif event_type == "tool_call":
                        tool_calls.append({
                            "name": event.get("name", "unknown"),
                            "args": event.get("args", {}),
                        })
                        live.update(create_streaming_display(
                            thinking_text=thinking_text,
                            response_text=response_text,
                            tool_calls=tool_calls,
                            tool_results=tool_results,
                            is_thinking=False,
                            is_responding=False,
                        ))

                    elif event_type == "tool_result":
                        tool_results.append({
                            "name": event.get("name", "unknown"),
                            "content": event.get("content", ""),
                        })
                        live.update(create_streaming_display(
                            thinking_text=thinking_text,
                            response_text=response_text,
                            tool_calls=tool_calls,
                            tool_results=tool_results,
                            is_thinking=False,
                            is_responding=False,
                        ))

                    elif event_type == "done":
                        if not response_text:
                            response_text = event.get("response", "")

            # 显示最终结果
            # 显示 thinking（简化版）
            if thinking_text:
                display_thinking = thinking_text
                if len(display_thinking) > 500:
                    display_thinking = display_thinking[:250] + "\n...\n" + display_thinking[-250:]
                console.print(Panel(
                    Text(display_thinking, style="dim"),
                    title="🧠 Thinking",
                    border_style="blue",
                ))

            # 显示工具调用和结果
            for i, tc in enumerate(tool_calls):
                console.print(f"[yellow]🔧 {tc['name']}[/yellow]")
                if tc.get("args"):
                    args_str = str(tc["args"])
                    if len(args_str) > 100:
                        args_str = args_str[:100] + "..."
                    console.print(f"[dim]   {args_str}[/dim]")
                # 显示对应的工具结果
                if i < len(tool_results):
                    tr = tool_results[i]
                    content = tr.get("content", "")
                    if len(content) > 300:
                        content = content[:300] + "..."
                    console.print(f"[cyan]📤 结果:[/cyan]")
                    console.print(f"[dim]   {content}[/dim]")

            # 显示响应
            if response_text:
                console.print(f"\n[bold blue]Assistant:[/bold blue]")
                console.print(Markdown(response_text))
                console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        description="LangChain Skills Agent - 演示 Skills 三层加载机制（支持流式输出和 Extended Thinking）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 列出发现的 Skills
  %(prog)s --list-skills

  # 显示 system prompt（演示 Level 1）
  %(prog)s --show-prompt

  # 执行请求（默认启用 thinking）
  %(prog)s "提取这篇公众号文章: https://mp.weixin.qq.com/s/xxx"

  # 执行请求（禁用 thinking）
  %(prog)s --no-thinking "列出当前目录的文件"

  # 交互式模式
  %(prog)s --interactive

Features:
  - 🧠 Extended Thinking: 显示模型的思考过程（蓝色面板）
  - 🔧 Tool Calls: 显示工具调用（黄色）
  - 💬 Streaming Response: 逐字显示响应（绿色面板）
""",
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="要执行的请求",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="进入交互式对话模式",
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="列出发现的 Skills",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="显示 system prompt（演示 Level 1）",
    )
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="禁用 Extended Thinking（可降低延迟和成本）",
    )
    parser.add_argument(
        "--cwd",
        type=str,
        help="设置工作目录",
    )

    args = parser.parse_args()

    # 设置工作目录
    if args.cwd:
        os.chdir(args.cwd)

    # thinking 开关
    enable_thinking = not args.no_thinking

    # 执行命令
    if args.list_skills:
        cmd_list_skills()
    elif args.show_prompt:
        cmd_show_prompt()
    elif args.interactive:
        cmd_interactive(enable_thinking=enable_thinking)
    elif args.prompt:
        cmd_run(args.prompt, enable_thinking=enable_thinking)
    else:
        # 默认进入交互模式
        cmd_interactive(enable_thinking=enable_thinking)


if __name__ == "__main__":
    main()
