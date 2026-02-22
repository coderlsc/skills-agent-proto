"""
会话消息存储模块

提供消息持久化到自定义业务表的功能，与 LangGraph checkpoint 系统独立。
此模块用于业务层面的消息查询和展示。
"""

from .message_store import MessageStore, MessageStoreConfig, get_message_store

__all__ = ["MessageStore", "MessageStoreConfig", "get_message_store"]
