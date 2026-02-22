"""
Checkpoint 配置管理模块

支持从环境变量加载配置，实现内存和 MySQL 两种存储模式
"""

import os
from dataclasses import dataclass, field
from typing import Optional


def _parse_int(value: Optional[str]) -> Optional[int]:
    """
    解析整数字符串

    Args:
        value: 字符串值

    Returns:
        解析后的整数，解析失败返回 None
    """
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@dataclass
class MySQLConfig:
    """MySQL 连接配置"""

    host: str
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = ""
    pool_size: Optional[int] = None
    max_overflow: Optional[int] = None


@dataclass
class CheckpointConfig:
    """Checkpoint 存储配置"""

    checkpoint_type: str  # "memory" or "mysql"
    mysql: Optional[MySQLConfig] = None


def get_checkpoint_config() -> CheckpointConfig:
    """
    从环境变量加载 checkpoint 配置

    环境变量:
        SKILLS_CHECKPOINT_TYPE: checkpoint 类型，"memory" (默认) 或 "mysql"
        SKILLS_MYSQL_HOST: MySQL 主机地址
        SKILLS_MYSQL_PORT: MySQL 端口，默认 3306
        SKILLS_MYSQL_USER: MySQL 用户名，默认 root
        SKILLS_MYSQL_PASSWORD: MySQL 密码
        SKILLS_MYSQL_DATABASE: MySQL 数据库名
        SKILLS_MYSQL_POOL_SIZE: 连接池大小（可选）
        SKILLS_MYSQL_MAX_OVERFLOW: 连接池最大溢出（可选）

    Returns:
        CheckpointConfig 配置对象

    Raises:
        ValueError: 配置无效时抛出
    """
    checkpoint_type = os.getenv("SKILLS_CHECKPOINT_TYPE", "memory").lower()

    # 验证 checkpoint 类型
    valid_types = {"memory", "mysql"}
    if checkpoint_type not in valid_types:
        raise ValueError(f"无效的 checkpoint 类型: {checkpoint_type}，必须是 {valid_types}")

    # 内存模式
    if checkpoint_type == "memory":
        return CheckpointConfig(checkpoint_type="memory")

    # MySQL 模式
    if checkpoint_type == "mysql":
        # 读取必需配置
        database = os.getenv("SKILLS_MYSQL_DATABASE")
        if not database:
            raise ValueError("MySQL 模式需要设置 SKILLS_MYSQL_DATABASE 环境变量")

        # 读取可选配置
        host = os.getenv("SKILLS_MYSQL_HOST", "localhost")
        port_str = os.getenv("SKILLS_MYSQL_PORT", "3306")
        user = os.getenv("SKILLS_MYSQL_USER", "root")
        password = os.getenv("SKILLS_MYSQL_PASSWORD", "")
        pool_size_str = os.getenv("SKILLS_MYSQL_POOL_SIZE")
        max_overflow_str = os.getenv("SKILLS_MYSQL_MAX_OVERFLOW")

        # 解析整数配置
        port = _parse_int(port_str)
        if port is None:
            raise ValueError("SKILLS_MYSQL_PORT 必须是有效的整数")

        pool_size = _parse_int(pool_size_str)
        if pool_size_str and pool_size is None:
            raise ValueError("SKILLS_MYSQL_POOL_SIZE 必须是有效的整数")

        max_overflow = _parse_int(max_overflow_str)
        if max_overflow_str and max_overflow is None:
            raise ValueError("SKILLS_MYSQL_MAX_OVERFLOW 必须是有效的整数")

        # 创建 MySQL 配置
        mysql_config = MySQLConfig(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )

        return CheckpointConfig(checkpoint_type="mysql", mysql=mysql_config)

    # 不应该到达这里
    return CheckpointConfig(checkpoint_type="memory")
