-- ===================================================================
-- Skills Agent 数据库初始化脚本
-- ===================================================================
--
-- 功能：创建 langchain_skills 数据库
-- 注意：表结构将在 Agent 首次启动时自动创建
--
-- 使用方法：
--   mysql -u root -p < scripts/init_database.sql
--
-- 或者登录 MySQL 后：
--   source scripts/init_database.sql
--
-- ===================================================================

-- 创建数据库（如果不存在）
-- 使用 utf8mb4_unicode_ci 以兼容 PyMySQLSaver
CREATE DATABASE IF NOT EXISTS langchain_skills
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE langchain_skills;

-- ===================================================================
-- 显示结果
-- ===================================================================

SELECT
    'Database created successfully!' AS status,
    'Tables will be created automatically on first Agent run' AS note,
    VERSION() AS mysql_version,
    DATABASE() AS current_database;
