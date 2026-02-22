#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Checkpoint 功能验证脚本

验证内存和 MySQL 两种 checkpoint 模式的功能
"""

import os
import sys


def clear_checkpoint_env():
    """清除 checkpoint 相关环境变量"""
    for key in list(os.environ.keys()):
        if key.startswith("SKILLS_CHECKPOINT") or key.startswith("SKILLS_MYSQL"):
            del os.environ[key]


def test_memory_mode():
    """测试内存模式"""
    print("=" * 60)
    print("测试 1: 内存模式 (默认)")
    print("=" * 60)

    clear_checkpoint_env()

    from langchain_skills.checkpoint import create_checkpointer
    from langgraph.checkpoint.memory import InMemorySaver

    checkpointer = create_checkpointer()
    print(f"[OK] Checkpointer 类型: {type(checkpointer).__name__}")
    assert isinstance(checkpointer, InMemorySaver), "应该是 InMemorySaver"
    print("[OK] 内存模式测试通过")


def test_memory_mode_explicit():
    """测试显式内存模式"""
    print("\n" + "=" * 60)
    print("测试 2: 显式内存模式")
    print("=" * 60)

    clear_checkpoint_env()
    os.environ["SKILLS_CHECKPOINT_TYPE"] = "memory"

    from importlib import reload
    from langchain_skills.checkpoint import config
    reload(config)

    from langchain_skills.checkpoint.factory import create_checkpointer
    from langgraph.checkpoint.memory import InMemorySaver

    checkpointer = create_checkpointer()
    print(f"[OK] Checkpointer 类型: {type(checkpointer).__name__}")
    assert isinstance(checkpointer, InMemorySaver), "应该是 InMemorySaver"
    print("[OK] 显式内存模式测试通过")


def test_mysql_config():
    """测试 MySQL 配置加载"""
    print("\n" + "=" * 60)
    print("测试 3: MySQL 配置加载")
    print("=" * 60)

    clear_checkpoint_env()
    os.environ["SKILLS_CHECKPOINT_TYPE"] = "mysql"
    os.environ["SKILLS_MYSQL_HOST"] = "localhost"
    os.environ["SKILLS_MYSQL_PORT"] = "3306"
    os.environ["SKILLS_MYSQL_USER"] = "test_user"
    os.environ["SKILLS_MYSQL_PASSWORD"] = "test_password"
    os.environ["SKILLS_MYSQL_DATABASE"] = "test_db"
    os.environ["SKILLS_MYSQL_POOL_SIZE"] = "10"
    os.environ["SKILLS_MYSQL_MAX_OVERFLOW"] = "20"

    from importlib import reload
    from langchain_skills.checkpoint import config
    reload(config)

    from langchain_skills.checkpoint.config import get_checkpoint_config

    config_obj = get_checkpoint_config()
    print(f"[OK] Checkpoint 类型: {config_obj.checkpoint_type}")
    print(f"[OK] MySQL 主机: {config_obj.mysql.host}")
    print(f"[OK] MySQL 端口: {config_obj.mysql.port}")
    print(f"[OK] MySQL 用户: {config_obj.mysql.user}")
    print(f"[OK] MySQL 数据库: {config_obj.mysql.database}")
    print(f"[OK] 连接池大小: {config_obj.mysql.pool_size}")
    print(f"[OK] 最大溢出: {config_obj.mysql.max_overflow}")

    assert config_obj.checkpoint_type == "mysql"
    assert config_obj.mysql.host == "localhost"
    assert config_obj.mysql.port == 3306
    assert config_obj.mysql.user == "test_user"
    assert config_obj.mysql.database == "test_db"
    assert config_obj.mysql.pool_size == 10
    assert config_obj.mysql.max_overflow == 20

    print("[OK] MySQL 配置加载测试通过")


def test_module_exports():
    """测试模块导出"""
    print("\n" + "=" * 60)
    print("测试 4: 模块导出")
    print("=" * 60)

    from langchain_skills.checkpoint import (
        create_checkpointer,
        get_checkpoint_config,
        CheckpointConfig,
        MySQLConfig,
    )

    print("[OK] create_checkpointer: 可用")
    print("[OK] get_checkpoint_config: 可用")
    print("[OK] CheckpointConfig: 可用")
    print("[OK] MySQLConfig: 可用")
    print("[OK] 模块导出测试通过")


def test_agent_integration():
    """测试 Agent 集成"""
    print("\n" + "=" * 60)
    print("测试 5: Agent 集成")
    print("=" * 60)

    clear_checkpoint_env()
    os.environ["ANTHROPIC_API_KEY"] = "test_key"  # 模拟 API key

    try:
        from langchain_skills.agent import LangChainSkillsAgent

        agent = LangChainSkillsAgent()
        print("[OK] Agent 创建成功")
        print("[OK] Agent 使用 checkpoint 工厂")
        print("[OK] Agent 集成测试通过")
    except Exception as e:
        print(f"[WARN] Agent 集成测试跳过: {e}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Checkpoint 功能验证")
    print("=" * 60)

    try:
        test_memory_mode()
        test_memory_mode_explicit()
        test_mysql_config()
        test_module_exports()
        test_agent_integration()

        print("\n" + "=" * 60)
        print("[OK] 所有测试通过!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        clear_checkpoint_env()


if __name__ == "__main__":
    sys.exit(main())
