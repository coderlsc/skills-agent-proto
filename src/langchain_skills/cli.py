"""
LangChain Skills Agent CLI

命令行入口，提供演示和交互功能：
- 列出发现的 Skills
- 显示 system prompt（演示 Level 1）
- 执行用户请求
- 交互式对话模式
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .agent import LangChainSkillsAgent
from .skill_loader import SkillLoader


# 加载环境变量
load_dotenv()

console = Console()


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


def cmd_run(prompt: str):
    """执行单次请求"""
    console.print(Panel(f"[bold cyan]User Request:[/bold cyan]\n{prompt}"))
    console.print()

    # 检查 API Key
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        console.print("Please set the environment variable or add it to .env file")
        sys.exit(1)

    agent = LangChainSkillsAgent()

    console.print("[dim]Running agent...[/dim]\n")

    try:
        # 流式输出
        last_result = None
        for chunk in agent.stream(prompt):
            last_result = chunk
            messages = chunk.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage):
                    # 打印工具调用
                    if last_msg.tool_calls:
                        for tool_call in last_msg.tool_calls:
                            console.print(f"[dim]🔧 Tool: {tool_call['name']}[/dim]")
                elif isinstance(last_msg, ToolMessage):
                    # 打印工具结果摘要
                    content = str(last_msg.content)[:100]
                    if len(str(last_msg.content)) > 100:
                        content += "..."
                    console.print(f"[dim]   Result: {content}[/dim]")

        # 打印最终响应
        if last_result:
            response = agent.get_last_response(last_result)
            if response:
                console.print()
                console.print(Panel(
                    Markdown(response),
                    title="Agent Response",
                    border_style="green",
                ))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise


def cmd_interactive():
    """交互式对话模式"""
    print_banner()

    # 检查 API Key
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        console.print("Please set the environment variable or add it to .env file")
        sys.exit(1)

    agent = LangChainSkillsAgent()

    # 显示发现的 Skills
    skills = agent.get_discovered_skills()
    console.print(f"\n[green]✓[/green] Discovered {len(skills)} skills")
    for skill in skills:
        console.print(f"  - {skill['name']}")
    console.print()

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

            # 运行 agent
            console.print()

            last_result = None
            for chunk in agent.stream(user_input, thread_id=thread_id):
                last_result = chunk
                messages = chunk.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                        for tool_call in last_msg.tool_calls:
                            console.print(f"[dim]🔧 {tool_call['name']}[/dim]")

            if last_result:
                response = agent.get_last_response(last_result)
                if response:
                    console.print(f"\n[bold blue]Assistant:[/bold blue]")
                    console.print(Markdown(response))
                    console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        description="LangChain Skills Agent - 演示 Skills 三层加载机制",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 列出发现的 Skills
  %(prog)s --list-skills

  # 显示 system prompt（演示 Level 1）
  %(prog)s --show-prompt

  # 执行请求
  %(prog)s "提取这篇公众号文章: https://mp.weixin.qq.com/s/xxx"

  # 交互式模式
  %(prog)s --interactive
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
        "--cwd",
        type=str,
        help="设置工作目录",
    )

    args = parser.parse_args()

    # 设置工作目录
    if args.cwd:
        os.chdir(args.cwd)

    # 执行命令
    if args.list_skills:
        cmd_list_skills()
    elif args.show_prompt:
        cmd_show_prompt()
    elif args.interactive:
        cmd_interactive()
    elif args.prompt:
        cmd_run(args.prompt)
    else:
        # 默认进入交互模式
        cmd_interactive()


if __name__ == "__main__":
    main()
