# 废弃脚本说明

以下脚本已被新的初始化流程替代，保留仅供参考。

## 已废弃脚本

| 废弃脚本 | 替代方案 | 原因 |
|----------|----------|------|
| `init_mysql.sql` | `init_database.sql` | 功能重复 |
| `reinit_mysql.sql` | `reset_database.sql` | 功能重复 |
| `init_clean.sql` | `init_database.sql` | 功能重复 |
| `rebuild_database.sql` | `reset_database.sql` | 手动创建表已不需要 |
| `fix_collation.sql` | `reset_database.sql` | 新脚本使用正确的排序规则 |
| `init_mysql_tables.py` | `init_all.py` 或 Agent 自动创建 | 表结构现在由代码自动创建 |
| `init_chat_tables.sql` | Agent 自动创建 | 表结构现在由代码自动创建 |
| `init_chat_tables.py` | `init_all.py` 或 Agent 自动创建 | 表结构现在由代码自动创建 |
| `migrate_add_tool_results.sql` | Agent 自动创建 | 新表已包含此字段 |
| `migrate_add_tool_results.py` | Agent 自动创建 | 新表已包含此字段 |

## 推荐脚本

| 脚本 | 用途 |
|------|------|
| `init_all.py` | 一键初始化（推荐） |
| `init_database.sql` | 仅创建数据库 |
| `reset_database.sql` | 重置数据库 |
| `verify_checkpoint.py` | 验证 checkpoint 功能 |

## 新的初始化流程

1. **推荐方式**：运行 `uv run python scripts/init_all.py`
2. **简单方式**：运行 `mysql -u root -p < scripts/init_database.sql` 然后启动 Agent
3. **自动方式**：Agent 首次启动时自动创建表（需要先创建数据库）

所有表结构现在由代码自动管理，无需手动执行 SQL 脚本。
