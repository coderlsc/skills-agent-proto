# Skills Agent 数据库设置指南

## 概述

本项目支持将 Agent 会话历史持久化到 MySQL 数据库，实现程序重启后对话历史的保留。

**重要更新**：表结构现在会在 Agent 首次启动时**自动创建**，无需手动初始化！

## 快速开始

### 方法一：一键初始化（推荐）

```bash
# 1. 配置环境变量（在 .env 文件中）
SKILLS_CHECKPOINT_TYPE=mysql
SKILLS_MYSQL_HOST=localhost
SKILLS_MYSQL_PORT=3306
SKILLS_MYSQL_USER=root
SKILLS_MYSQL_PASSWORD=your_password
SKILLS_MYSQL_DATABASE=langchain_skills

# 2. 运行一键初始化脚本
uv run python scripts/init_all.py

# 3. 启动 Agent（表会自动创建）
uv run langchain-skills --interactive
```

### 方法二：仅创建数据库

```bash
# 1. 创建数据库
mysql -u root -p < scripts/init_database.sql

# 2. 启动 Agent（表会自动创建）
uv run langchain-skills --interactive
```

### 方法三：完全手动

```bash
# 1. 登录 MySQL
mysql -u root -p

# 2. 创建数据库
CREATE DATABASE langchain_skills
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

# 3. 退出并启动 Agent
exit
uv run langchain-skills --interactive
```

## 自动创建的表

Agent 首次启动时会自动创建以下表：

### Checkpoint 表（LangGraph）

- `checkpoint_migrations` - 迁移版本跟踪
- `checkpoints` - 会话 checkpoint 数据
- `checkpoint_blobs` - 大型二进制数据
- `checkpoint_writes` - 中间写入结果

### 会话管理表

- `chat_sessions` - 会话摘要（标题、消息数量等）
- `chat_message_details` - 消息明细（内容、思考过程、工具调用等）

## 环境变量配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SKILLS_CHECKPOINT_TYPE` | checkpoint 类型（memory/mysql） | memory |
| `SKILLS_MYSQL_HOST` | MySQL 主机地址 | localhost |
| `SKILLS_MYSQL_PORT` | MySQL 端口 | 3306 |
| `SKILLS_MYSQL_USER` | MySQL 用户名 | root |
| `SKILLS_MYSQL_PASSWORD` | MySQL 密码 | - |
| `SKILLS_MYSQL_DATABASE` | MySQL 数据库名 | langchain_skills |
| `SKILLS_MYSQL_POOL_SIZE` | 连接池大小（可选） | - |
| `SKILLS_MYSQL_MAX_OVERFLOW` | 连接池最大溢出（可选） | - |

## 验证安装

### 检查表是否创建成功

```sql
USE langchain_skills;
SHOW TABLES;
```

应该看到以下表：
```
+-------------------------+
| Tables_in_langchain_skills |
+-------------------------+
| chat_message_details    |
| chat_sessions           |
| checkpoint_blobs        |
| checkpoint_migrations   |
| checkpoint_writes       |
| checkpoints             |
+-------------------------+
```

### 查看表结构

```sql
-- 查看会话表结构
DESC chat_sessions;

-- 查看消息表结构
DESC chat_message_details;

-- 查看 checkpoint 表结构
DESC checkpoints;
```

## 数据库重置

如需完全重置数据库（删除所有数据）：

```bash
# 方法一：使用重置脚本
mysql -u root -p < scripts/reset_database.sql

# 方法二：手动执行
mysql -u root -p -e "DROP DATABASE IF EXISTS langchain_skills; CREATE DATABASE langchain_skills CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## 故障排除

### 连接失败

确保 MySQL 服务正在运行：

```bash
# Windows
net start MySQL80

# Linux/Mac
sudo systemctl start mysql
# 或
sudo service mysql start
```

### 认证问题

如果使用 `caching_sha2_password` 认证遇到问题，可以创建使用 `mysql_native_password` 的用户：

```sql
CREATE USER 'langchain'@'localhost' IDENTIFIED WITH mysql_native_password BY 'password';
GRANT ALL PRIVILEGES ON langchain_skills.* TO 'langchain'@'localhost';
FLUSH PRIVILEGES;
```

然后更新 `.env` 文件：
```bash
SKILLS_MYSQL_USER=langchain
SKILLS_MYSQL_PASSWORD=password
```

### 表创建失败

如果表创建失败，检查：

1. 数据库是否存在：`SHOW DATABASES;`
2. 用户权限是否足够：`SHOW GRANTS FOR 'root'@'localhost';`
3. 查看错误日志：启动 Agent 时会显示详细错误信息

## 使用示例

```python
from langchain_skills.agent import LangChainSkillsAgent

# 创建 Agent（会自动使用 MySQL 持久化）
agent = LangChainSkillsAgent()

# 使用相同的 thread_id 可以恢复历史对话
response1 = agent.stream("你好", thread_id="user-123")
response2 = agent.stream("上一题是什么？", thread_id="user-123")

# 程序重启后，使用相同的 thread_id 仍可访问历史
```

## 性能优化

### 连接池配置

在 `.env` 中配置连接池参数：

```bash
SKILLS_MYSQL_POOL_SIZE=5
SKILLS_MYSQL_MAX_OVERFLOW=10
```

### 索引说明

表已包含以下索引以提高查询性能：

**chat_sessions**:
- `idx_thread_id` - thread_id 索引
- `idx_updated_at` - 更新时间索引（降序）

**chat_message_details**:
- `idx_thread_id` - thread_id 索引
- `idx_created_at` - 创建时间索引（降序）

**Checkpoint 表**：
- 由 PyMySQLSaver 自动创建和管理

## 技术细节

### 字符集和排序规则

- 数据库字符集：`utf8mb4`
- 排序规则：`utf8mb4_unicode_ci`
- 完整支持 Unicode 和 Emoji

### 数据类型

- checkpoint 和 metadata 使用 JSON 类型
- 大型数据使用 LONGBLOB（最大 4GB）
- 字符串字段使用 VARCHAR(255)

### 自动初始化流程

1. Agent 启动时检测 `SKILLS_CHECKPOINT_TYPE=mysql`
2. 创建 PyMySQLSaver 连接
3. 调用 `saver.setup()` 初始化 checkpoint 表
4. 创建 MessageStore 实例
5. 调用 `store.setup()` 初始化会话管理表
6. 所有操作都是幂等的，可以安全地多次执行

## Scripts 目录说明

| 脚本 | 用途 |
|------|------|
| `init_all.py` | 一键初始化（创建数据库 + 所有表） |
| `init_database.sql` | 仅创建数据库（表由 Agent 自动创建） |
| `reset_database.sql` | 重置数据库（删除并重新创建） |
| `verify_checkpoint.py` | 验证 checkpoint 功能 |

**注意**：以下脚本已废弃，请使用 `init_all.py` 代替：
- `init_mysql.sql` → 使用 `init_database.sql`
- `init_mysql_tables.py` → 由 Agent 自动创建
- `init_chat_tables.sql` → 由 Agent 自动创建
- `init_chat_tables.py` → 由 Agent 自动创建
- `reinit_mysql.sql` → 使用 `reset_database.sql`
- `rebuild_database.sql` → 使用 `reset_database.sql`
