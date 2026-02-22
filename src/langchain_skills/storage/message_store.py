"""
消息存储实现

解析 LangChain 消息对象并存入业务明细表，用于会话历史查询。
"""

from __future__ import annotations

import json
import pymysql
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


@dataclass
class MessageStoreConfig:
    """消息存储配置"""

    host: str
    port: int
    user: str
    password: str
    database: str


class MessageStore:
    """
    消息存储类

    负责将 LangChain 消息对象持久化到自定义业务表，
    支持会话列表查询和消息历史加载。
    """

    def __init__(self, config: MessageStoreConfig):
        self.config = config
        self._conn: Optional[pymysql.connections.Connection] = None

    def setup(self) -> None:
        """
        初始化数据库表结构

        创建会话管理所需的表（如果不存在）。
        此方法是幂等的，可以安全地多次调用。
        """
        conn = self.get_connection()
        with conn.cursor() as cursor:
            # 创建 chat_sessions 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                    thread_id VARCHAR(255) NOT NULL UNIQUE COMMENT '对应 LangGraph thread_id',
                    title VARCHAR(500) NOT NULL DEFAULT 'New Conversation' COMMENT '会话标题',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    message_count INT NOT NULL DEFAULT 0 COMMENT '消息数量',
                    INDEX idx_thread_id (thread_id),
                    INDEX idx_updated_at (updated_at DESC)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='会话表'
            """)

            # 创建 chat_message_details 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_message_details (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                    thread_id VARCHAR(255) NOT NULL COMMENT '对应 thread_id',
                    role ENUM('human', 'ai', 'tool', 'system') NOT NULL COMMENT '消息角色',
                    content TEXT COMMENT '消息内容',
                    reasoning_content TEXT COMMENT 'AI 思考过程 (Extended Thinking)',
                    tool_calls JSON COMMENT '工具调用列表',
                    tool_results JSON COMMENT '工具调用结果，以 tool_call id 为键',
                    tool_call_id VARCHAR(255) COMMENT '工具调用 ID (tool 消息)',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    INDEX idx_thread_id (thread_id),
                    INDEX idx_created_at (created_at DESC),
                    FOREIGN KEY (thread_id) REFERENCES chat_sessions(thread_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='消息明细表'
            """)

    def get_connection(self) -> pymysql.connections.Connection:
        """获取数据库连接（延迟初始化）"""
        if self._conn is None:
            self._conn = pymysql.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                autocommit=True,
                charset="utf8mb4",
            )
        return self._conn

    def save_message(self, thread_id: str, message: "BaseMessage") -> None:
        """
        保存消息到数据库

        Args:
            thread_id: 会话线程 ID
            message: LangChain 消息对象 (HumanMessage/AIMessage/ToolMessage)
        """
        # 提取基础字段
        role = message.type
        content = ""
        reasoning_content = ""
        tool_calls = None
        tool_results = None
        tool_call_id = None

        # 处理内容（可能是字符串或列表）
        if isinstance(message.content, str):
            content = message.content
        elif isinstance(message.content, list):
            # 多部分内容（如包含文本和图片）
            text_parts = []
            for part in message.content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            content = "\n".join(text_parts)

        # 根据消息类型提取特定字段
        if hasattr(message, "additional_kwargs"):
            # AIMessage 可能有思考过程和工具调用结果
            add_kwargs = message.additional_kwargs
            reasoning_content = (
                add_kwargs.get("reasoning_content")
                or add_kwargs.get("thought")
                or add_kwargs.get("thinking")
                or ""
            )
            # 提取 tool_results
            if "tool_results" in add_kwargs:
                tool_results = json.dumps(add_kwargs["tool_results"], ensure_ascii=False)

        if hasattr(message, "tool_calls") and message.tool_calls:
            # AIMessage 的工具调用列表
            tool_calls = json.dumps(message.tool_calls, ensure_ascii=False)

        if hasattr(message, "tool_call_id") and message.tool_call_id:
            # ToolMessage 的工具调用 ID
            tool_call_id = message.tool_call_id

        # 写入数据库
        conn = self.get_connection()
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO chat_message_details
                (thread_id, role, content, reasoning_content, tool_calls, tool_results, tool_call_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(
                sql,
                (
                    thread_id,
                    role,
                    content,
                    reasoning_content,
                    tool_calls,
                    tool_results,
                    tool_call_id,
                ),
            )

            # 更新会话消息计数
            self._increment_message_count(thread_id)

    def ensure_session(
        self, thread_id: str, title: str = "New Conversation"
    ) -> None:
        """
        确保会话记录存在

        如果会话不存在则创建，存在则更新 updated_at 时间戳。

        Args:
            thread_id: 会话线程 ID
            title: 会话标题（仅新建时使用）
        """
        conn = self.get_connection()
        with conn.cursor() as cursor:
            # 尝试更新时间戳
            cursor.execute(
                "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = %s",
                (thread_id,),
            )
            if cursor.rowcount == 0:
                # 不存在则插入新记录
                cursor.execute(
                    "INSERT INTO chat_sessions (thread_id, title) VALUES (%s, %s)",
                    (thread_id, title[:500]),  # 限制标题长度
                )

    def _increment_message_count(self, thread_id: str) -> None:
        """增加会话消息计数"""
        conn = self.get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE chat_sessions
                SET message_count = message_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE thread_id = %s
                """,
                (thread_id,),
            )

    def get_sessions(self, limit: int = 50) -> list[dict]:
        """
        获取会话列表

        Args:
            limit: 最大返回数量

        Returns:
            会话列表，按更新时间倒序
        """
        conn = self.get_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, thread_id, title, created_at, updated_at, message_count
                FROM chat_sessions
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cursor.fetchall()

    def get_messages(self, thread_id: str, limit: int = 100) -> list[dict]:
        """
        获取会话消息

        Args:
            thread_id: 会话线程 ID
            limit: 最大返回数量

        Returns:
            消息列表，按创建时间正序
        """
        conn = self.get_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                """
                SELECT id, role, content, reasoning_content, tool_calls, tool_results, tool_call_id, created_at
                FROM chat_message_details
                WHERE thread_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (thread_id, limit),
            )
            return cursor.fetchall()

    def update_session_title(self, thread_id: str, title: str) -> bool:
        """
        更新会话标题

        Args:
            thread_id: 会话线程 ID
            title: 新标题

        Returns:
            是否更新成功
        """
        conn = self.get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE chat_sessions SET title = %s WHERE thread_id = %s",
                (title[:500], thread_id),
            )
            return cursor.rowcount > 0

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None


# 全局单例
_store_instance: Optional[MessageStore] = None


def get_message_store() -> Optional[MessageStore]:
    """
    获取消息存储单例

    从环境变量读取 MySQL 配置并创建 MessageStore 实例。
    如果配置不完整或未启用 MySQL，返回 None。

    Returns:
        MessageStore 实例或 None
    """
    global _store_instance

    if _store_instance is not None:
        return _store_instance

    import os

    # 检查是否启用 MySQL
    checkpoint_type = os.getenv("SKILLS_CHECKPOINT_TYPE", "memory").lower()
    if checkpoint_type != "mysql":
        return None

    # 读取配置
    try:
        config = MessageStoreConfig(
            host=os.getenv("SKILLS_MYSQL_HOST", "localhost"),
            port=int(os.getenv("SKILLS_MYSQL_PORT", "3306")),
            user=os.getenv("SKILLS_MYSQL_USER", "root"),
            password=os.getenv("SKILLS_MYSQL_PASSWORD", ""),
            database=os.getenv("SKILLS_MYSQL_DATABASE", "langchain_skills"),
        )
        _store_instance = MessageStore(config)
        # 自动初始化表结构（幂等操作）
        try:
            _store_instance.setup()
        except Exception as setup_error:
            # 如果 setup 失败，记录日志但不中断启动
            import warnings
            warnings.warn(f"消息存储表初始化警告: {setup_error}")
        return _store_instance
    except Exception:
        return None
