"""SQLite 数据库操作。

使用 Python 内置 sqlite3 模块，数据库文件为 backend/quant.db。
"""

import sqlite3
from contextlib import contextmanager

from config import DB_PATH

# 建表 SQL（IF NOT EXISTS 保证重复执行安全）
SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,          -- 队伍登录名
    display_name TEXT NOT NULL,         -- 显示名称
    password TEXT NOT NULL,             -- 登录密码
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,           -- 关联队伍
    data_track TEXT NOT NULL,           -- 数据轨道：learning_1/learning_2/learning_3/hidden
    status TEXT DEFAULT 'pending',      -- pending/running/success/failed
    score REAL,                         -- 综合评分
    metrics TEXT,                       -- JSON 格式的详细指标
    file_path TEXT,                     -- 策略文件保存路径
    error_message TEXT,                 -- 错误信息
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scored_at TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);
"""


def init_db():
    """创建所有数据表。"""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """数据库连接上下文管理器：自动提交、回滚并关闭。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 允许按列名访问结果
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
