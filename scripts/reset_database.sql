-- ===================================================================
-- Skills Agent 数据库重置脚本
-- ===================================================================
--
-- 警告：此脚本会删除现有的 langchain_skills 数据库及其所有数据！
-- 仅在需要完全重置时使用。
--
-- 使用方法：
--   mysql -u root -p < scripts/reset_database.sql
--
-- 或者登录 MySQL 后：
--   source scripts/reset_database.sql
--
-- ===================================================================

-- 删除现有数据库（如果存在）
DROP DATABASE IF EXISTS langchain_skills;

-- 重新创建数据库
CREATE DATABASE langchain_skills
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE langchain_skills;

-- ===================================================================
-- 显示结果
-- ===================================================================

SELECT
    'Database reset successfully!' AS status,
    'Run Agent to create tables automatically' AS note,
    VERSION() AS mysql_version,
    DATABASE() AS current_database;
