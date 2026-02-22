#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skills Agent 数据库一键初始化脚本

功能：
1. 创建数据库（如果不存在）
2. 初始化 LangGraph checkpoint 表
3. 初始化会话管理表

使用方法：
    uv run python scripts/init_all.py

环境变量：
    SKILLS_CHECKPOINT_TYPE=mysql
    SKILLS_MYSQL_HOST=localhost
    SKILLS_MYSQL_PORT=3306
    SKILLS_MYSQL_USER=root
    SKILLS_MYSQL_PASSWORD=your_password
    SKILLS_MYSQL_DATABASE=langchain_skills
"""

import os
import sys


def print_header(title: str) -> None:
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_step(step: str, status: str = "INFO") -> None:
    """打印步骤"""
    prefix = {
        "INFO": "[INFO]",
        "OK": "[OK]  ",
        "WARN": "[WARN]",
        "ERROR": "[ERROR]",
    }.get(status, "[INFO]")
    print(f"{prefix} {step}")


def check_env() -> bool:
    """检查环境变量配置"""
    print_header("步骤 1: 检查环境变量")

    checkpoint_type = os.getenv("SKILLS_CHECKPOINT_TYPE", "memory").lower()

    if checkpoint_type != "mysql":
        print_step("SKILLS_CHECKPOINT_TYPE 未设置为 'mysql'", "ERROR")
        print("\n请设置以下环境变量后重试：")
        print("  SKILLS_CHECKPOINT_TYPE=mysql")
        print("  SKILLS_MYSQL_HOST=localhost")
        print("  SKILLS_MYSQL_PORT=3306")
        print("  SKILLS_MYSQL_USER=root")
        print("  SKILLS_MYSQL_PASSWORD=your_password")
        print("  SKILLS_MYSQL_DATABASE=langchain_skills")
        return False

    print_step("SKILLS_CHECKPOINT_TYPE=mysql", "OK")
    print_step(f"主机: {os.getenv('SKILLS_MYSQL_HOST', 'localhost')}")
    print_step(f"端口: {os.getenv('SKILLS_MYSQL_PORT', '3306')}")
    print_step(f"用户: {os.getenv('SKILLS_MYSQL_USER', 'root')}")
    print_step(f"数据库: {os.getenv('SKILLS_MYSQL_DATABASE', 'langchain_skills')}")

    return True


def create_database() -> bool:
    """创建数据库"""
    print_header("步骤 2: 创建数据库")

    import pymysql

    host = os.getenv("SKILLS_MYSQL_HOST", "localhost")
    port = int(os.getenv("SKILLS_MYSQL_PORT", "3306"))
    user = os.getenv("SKILLS_MYSQL_USER", "root")
    password = os.getenv("SKILLS_MYSQL_PASSWORD", "")
    database = os.getenv("SKILLS_MYSQL_DATABASE", "langchain_skills")

    try:
        # 连接 MySQL（不指定数据库）
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8mb4",
        )
        cursor = conn.cursor()

        # 创建数据库
        cursor.execute(
            f"""
            CREATE DATABASE IF NOT EXISTS `{database}`
            CHARACTER SET utf8mb4
            COLLATE utf8mb4_unicode_ci
        """
        )
        print_step(f"数据库 '{database}' 已准备就绪", "OK")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print_step(f"创建数据库失败: {e}", "ERROR")
        return False


def init_checkpoint_tables() -> bool:
    """初始化 checkpoint 表"""
    print_header("步骤 3: 初始化 Checkpoint 表")

    try:
        from langchain_skills.checkpoint import create_checkpointer

        print_step("创建 PyMySQLSaver 连接...")
        checkpointer = create_checkpointer()

        print_step("执行表迁移...")
        checkpointer.setup()

        print_step("Checkpoint 表初始化完成", "OK")
        print("\n创建的表:")
        print("  - checkpoint_migrations (迁移版本跟踪)")
        print("  - checkpoints (会话 checkpoint 数据)")
        print("  - checkpoint_blobs (大型二进制数据)")
        print("  - checkpoint_writes (中间写入结果)")

        return True

    except Exception as e:
        print_step(f"Checkpoint 表初始化失败: {e}", "ERROR")
        import traceback

        traceback.print_exc()
        return False


def init_chat_tables() -> bool:
    """初始化会话管理表"""
    print_header("步骤 4: 初始化会话管理表")

    try:
        from langchain_skills.storage import get_message_store

        print_step("获取 MessageStore 实例...")
        store = get_message_store()

        if store is None:
            print_step("MessageStore 未启用（跳过）", "WARN")
            return True

        print_step("创建会话管理表...")
        store.setup()

        print_step("会话管理表初始化完成", "OK")
        print("\n创建的表:")
        print("  - chat_sessions (会话摘要)")
        print("  - chat_message_details (消息明细)")

        return True

    except Exception as e:
        print_step(f"会话管理表初始化失败: {e}", "ERROR")
        import traceback

        traceback.print_exc()
        return False


def verify_tables() -> bool:
    """验证表创建成功"""
    print_header("步骤 5: 验证表结构")

    import pymysql

    host = os.getenv("SKILLS_MYSQL_HOST", "localhost")
    port = int(os.getenv("SKILLS_MYSQL_PORT", "3306"))
    user = os.getenv("SKILLS_MYSQL_USER", "root")
    password = os.getenv("SKILLS_MYSQL_PASSWORD", "")
    database = os.getenv("SKILLS_MYSQL_DATABASE", "langchain_skills")

    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
        )
        cursor = conn.cursor()

        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

        print_step(f"数据库中共有 {len(tables)} 张表", "OK")

        # 分类显示
        checkpoint_tables = [t for t in tables if t.startswith("checkpoint")]
        chat_tables = [t for t in tables if t.startswith("chat")]

        if checkpoint_tables:
            print("\nCheckpoint 表:")
            for t in checkpoint_tables:
                print(f"  ✓ {t}")

        if chat_tables:
            print("\n会话管理表:")
            for t in chat_tables:
                print(f"  ✓ {t}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print_step(f"验证失败: {e}", "ERROR")
        return False


def main() -> int:
    """主函数"""
    print("\n" + "=" * 60)
    print("  Skills Agent 数据库初始化")
    print("=" * 60)

    try:
        # 检查环境变量
        if not check_env():
            return 1

        # 创建数据库
        if not create_database():
            return 1

        # 初始化 checkpoint 表
        if not init_checkpoint_tables():
            return 1

        # 初始化会话管理表
        if not init_chat_tables():
            return 1

        # 验证表创建
        if not verify_tables():
            return 1

        # 成功
        print_header("初始化完成！")
        print("\n现在可以启动 Agent：")
        print("  uv run langchain-skills --interactive")
        print("  uv run langchain-skills-web")
        print()
        return 0

    except KeyboardInterrupt:
        print("\n\n[INFO] 操作已取消")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
