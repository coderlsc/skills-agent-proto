"""
Checkpoint 工厂模块

提供创建 checkpointer 实例的工厂函数
"""

from typing import Union

import pymysql
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver

from .config import get_checkpoint_config


def create_checkpointer() -> Union[InMemorySaver, PyMySQLSaver]:
    """
    创建 checkpointer 实例

    根据环境变量配置返回对应的 checkpointer:
    - 内存模式 (默认): InMemorySaver
    - MySQL 模式: PyMySQLSaver

    Returns:
        InMemorySaver 或 PyMySQLSaver 实例

    Raises:
        ValueError: 配置无效时抛出
        ConnectionError: MySQL 连接失败时抛出
    """
    config = get_checkpoint_config()

    if config.checkpoint_type == "memory":
        return InMemorySaver()

    if config.checkpoint_type == "mysql":
        return _create_mysql_saver(config.mysql)

    # 不应该到达这里
    return InMemorySaver()


def _create_mysql_saver(mysql_config):
    """
    创建 PyMySQLSaver 实例

    Args:
        mysql_config: MySQLConfig 配置对象

    Returns:
        PyMySQLSaver 实例

    Raises:
        ConnectionError: MySQL 连接失败时抛出
    """
    try:
        # 创建 pymysql 连接
        conn = pymysql.connect(
            host=mysql_config.host,
            port=mysql_config.port,
            user=mysql_config.user,
            password=mysql_config.password,
            database=mysql_config.database,
            autocommit=True,
        )
        # 创建 PyMySQLSaver 实例
        saver = PyMySQLSaver(conn)

        # 初始化表结构（如果不存在）
        # setup() 是幂等的，可以安全地多次调用
        try:
            saver.setup()
        except Exception as setup_error:
            # 如果 setup 失败，记录日志但不中断启动
            # 表可能已经存在，或者会在首次使用时创建
            import warnings
            warnings.warn(f"表初始化警告: {setup_error}")

        return saver
    except Exception as e:
        raise ConnectionError(f"无法连接到 MySQL 数据库: {e}") from e
