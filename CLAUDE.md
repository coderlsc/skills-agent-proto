# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

使用 LangChain 1.0 构建的 Skills Agent，演示 Anthropic Skills 三层加载机制的底层原理。包含完整的 CLI 和 Web UI，支持流式输出、Extended Thinking 和会话持久化。

## 常用命令

### 基础开发

```bash
# 安装依赖
uv sync

# 运行测试
uv run python -m pytest tests/ -v

# 运行单个测试文件
uv run python -m pytest tests/test_stream.py -v

# 运行特定测试
uv run python -m pytest tests/test_stream.py::TestToolCallTracker -v
```

### CLI 模式

```bash
# 交互式运行
uv run langchain-skills --interactive

# 单次执行
uv run langchain-skills "列出当前目录"

# 查看发现的 Skills
uv run langchain-skills --list-skills

# 查看 System Prompt
uv run langchain-skills --show-prompt

# 禁用 Thinking（降低延迟）
uv run langchain-skills --no-thinking "执行 pwd"
```

### Web 开发

```bash
# 一键启动（推荐）：同时启动后端和前端
./start.sh

# 仅启动后端 API（默认端口 8001）
uv run langchain-skills-web
# 等价于：uv run uvicorn langchain_skills.web_api:app --reload --port 8001

# 仅启动前端（默认端口 5173）
cd web
npm install
npm run dev

# 自定义端口启动
BACKEND_PORT=8002 FRONTEND_PORT=5174 ./start.sh
```

### MySQL 数据库初始化

```bash
# 创建数据库
mysql -u root -p < scripts/init_mysql.sql

# 初始化表结构（方法 A：使用脚本）
uv run python scripts/init_mysql_tables.py

# 初始化表结构（方法 B：首次运行自动创建）
# Agent 会在首次使用时自动创建表结构
```

## 核心架构

### Skills 三层加载机制

| 层级 | 时机 | 实现 |
|------|------|------|
| **Level 1** | 启动时 | `SkillLoader.scan_skills()` 扫描目录，解析 YAML frontmatter，注入 system_prompt |
| **Level 2** | 请求匹配时 | `load_skill` 工具读取 SKILL.md 完整指令 |
| **Level 3** | 执行时 | `bash` 工具执行脚本，脚本代码不进入上下文 |

核心设计：让大模型成为真正的"智能体"，自己阅读指令、发现脚本、决定执行。

### 流式处理架构

```
agent.py: stream_events() → 使用 stream_mode="messages" 获取 LangChain 流式输出
    ↓
stream/tracker.py: ToolCallTracker 追踪工具调用，处理增量 JSON (input_json_delta)
    ↓
stream/emitter.py: StreamEventEmitter 生成标准化事件 (thinking/text/tool_call/tool_result/done)
    ↓
stream/formatter.py: ToolResultFormatter 格式化输出，检测 [OK]/[FAILED] 前缀
    ↓
cli.py: Rich Live Display 渲染到终端
    ↓ (或 Web SSE)
web_api.py: SSE 推送到前端
```

**事件类型**：
- `thinking`: Extended Thinking 内容
- `text`: 响应文本
- `tool_call`: 工具调用（name, args, id）
- `tool_result`: 工具结果（content, tool_use_id, success）
- `done`: 完成标记
- `error`: 错误信息

### 关键流程：工具调用参数处理

LangChain 流式传输中，工具参数可能分批到达：
1. `tool_use` 块先到达（`input` 可能为 `None` 或 `{}`）
2. `input_json_delta` 分批传递参数片段
3. `finalize_all()` 在收到 `tool_result` 前解析完整 JSON

CLI 使用 `tool_id` 去重，允许同一工具调用发送多次（首次显示"执行中"，finalize 后更新完整参数）。

### Checkpoint 和存储模块

**Checkpoint 模块** (`src/langchain_skills/checkpoint/`):
- `config.py`: 配置管理（CheckpointConfig、MySQLConfig）
- `factory.py`: Checkpointer 工厂（create_checkpointer）
- 支持内存存储（InMemorySaver）和 MySQL 持久化（PyMySQLSaver）
- 表：`checkpoints`、`checkpoints_blobs`

**消息存储模块** (`src/langchain_skills/storage/message_store.py`):
- `MessageStore`: 业务层面的消息持久化
- `save_message()`: 保存消息到 `chat_message_details` 表
- `get_sessions()`: 获取会话列表
- `get_messages()`: 获取会话消息历史
- 表：`chat_sessions`、`chat_message_details`

### Web 前端架构

**技术栈**: React 19.2.0 + TypeScript + Vite 7.2.4

**核心文件**:
- `App.tsx`: 主应用，SSE 连接管理
- `state/chatReducer.ts`: 状态管理（useReducer）
- `lib/sse.ts`: SSE 客户端封装
- `types/events.ts`: 类型定义

**状态管理**:
- `ChatState`: 全局状态（skills、threads、sessions）
- `ThreadState`: 单个线程状态
- `TimelineEntry`: 时间线条目（user/assistant/system）
- `ToolCallView`: 工具调用视图

**组件**:
- `SkillsPanel`: Skills 列表
- `SessionPanel`: 会话历史面板
- `ChatArea`: 聊天区域

## 代码约定

### 工具输出格式

bash 工具使用 `[OK]`/`[FAILED]` 前缀标识执行状态：
```
[OK]

output content...

[FAILED] Exit code: 1

--- stderr ---
error message
```

### Skills 目录结构

```
.claude/skills/skill-name/
├── SKILL.md          # 必需：YAML frontmatter + 指令
├── scripts/          # 可选：可执行脚本
├── references/       # 可选：参考文档
└── assets/           # 可选：模板和资源
```

Skills 搜索路径（优先级从高到低）：
1. `.claude/skills/` (项目级)
2. `~/.claude/skills/` (用户级)

## 重要文件路径

### 核心逻辑
- `src/langchain_skills/agent.py` - Agent 主逻辑
- `src/langchain_skills/skill_loader.py` - Skills 加载器
- `src/langchain_skills/tools.py` - 工具定义
- `src/langchain_skills/cli.py` - CLI 入口

### 流式处理
- `src/langchain_skills/stream/emitter.py` - 事件发射器
- `src/langchain_skills/stream/tracker.py` - 工具调用追踪
- `src/langchain_skills/stream/formatter.py` - 结果格式化
- `src/langchain_skills/stream/utils.py` - 工具函数

### 存储
- `src/langchain_skills/checkpoint/factory.py` - Checkpoint 工厂
- `src/langchain_skills/checkpoint/config.py` - 配置管理
- `src/langchain_skills/storage/message_store.py` - 消息存储

### Web
- `src/langchain_skills/web_api.py` - FastAPI 应用
- `web/src/App.tsx` - React 主应用
- `web/src/state/chatReducer.ts` - 状态管理
- `web/src/lib/sse.ts` - SSE 客户端

### 配置
- `pyproject.toml` - Python 项目配置
- `start.sh` - 启动脚本
- `.env.example` - 环境变量模板

## 环境变量

### 认证配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` | API Key | 必填 |
| `ANTHROPIC_BASE_URL` | 代理地址 | 官方 API |

### 模型配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CLAUDE_MODEL` | 模型名称 | claude-opus-4-5-20251101 |
| `MAX_TOKENS` | 最大 tokens | 16000 |
| `MAX_TURNS` | 最大对话轮数 | 20 |

### Checkpoint 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SKILLS_CHECKPOINT_TYPE` | checkpoint 类型（memory/mysql） | memory |
| `SKILLS_MYSQL_HOST` | MySQL 主机地址 | localhost |
| `SKILLS_MYSQL_PORT` | MySQL 端口 | 3306 |
| `SKILLS_MYSQL_USER` | MySQL 用户名 | root |
| `SKILLS_MYSQL_PASSWORD` | MySQL 密码 | - |
| `SKILLS_MYSQL_DATABASE` | MySQL 数据库名 | - |
| `SKILLS_MYSQL_POOL_SIZE` | 连接池大小（可选） | - |
| `SKILLS_MYSQL_MAX_OVERFLOW` | 连接池最大溢出（可选） | - |

### Web 服务配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SKILLS_WEB_HOST` | Web 服务监听地址 | 0.0.0.0 |
| `SKILLS_WEB_PORT` | Web 服务端口 | 8001 |
| `SKILLS_WEB_RELOAD` | 启用自动重载 | true |

### 前端配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE_URL` | 后端 API 地址 | http://127.0.0.1:8001 |

## 数据库表结构

### LangGraph Checkpoint 表

```sql
-- checkpoints: 存储检查点元数据
CREATE TABLE checkpoints (
    thread_id TEXT,
    checkpoint_ns TEXT,
    checkpoint_id TEXT,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint BLOB,
    metadata BLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- checkpoints_blobs: 存储大型二进制数据
CREATE TABLE checkpoints_blobs (
    thread_id TEXT,
    checkpoint_ns TEXT,
    checkpoint_id TEXT,
    blob BLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
```

### 业务消息表

```sql
-- chat_sessions: 会话摘要
CREATE TABLE chat_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    thread_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255),
    message_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- chat_message_details: 消息详情
CREATE TABLE chat_message_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    thread_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT,
    reasoning_content TEXT,
    tool_calls JSON,
    tool_results JSON,
    tool_call_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_thread_id (thread_id)
);
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/skills` | GET | 获取发现的 Skills 列表 |
| `/api/prompt` | GET | 获取当前 System Prompt |
| `/api/chat/stream` | GET | SSE 流式聊天接口 |
| `/api/sessions` | GET | 获取会话列表 |
| `/api/sessions/{thread_id}/messages` | GET | 获取会话消息历史 |

## 测试结构

```
tests/
├── test_stream.py          # 流式处理测试
│   ├── TestStreamEventEmitter
│   ├── TestToolCallTracker
│   ├── TestToolResultFormatter
│   └── TestStreamUtils
├── test_cli.py             # CLI 功能测试
├── test_tools.py           # 工具函数测试
├── test_web_api.py         # Web API 测试
└── test_checkpoint/        # Checkpoint 模块测试
    ├── test_config.py
    ├── test_factory.py
    └── test_integration.py
```
