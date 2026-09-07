"""配置管理。"""

from pathlib import Path

# backend 目录（本文件所在目录）
BASE_DIR = Path(__file__).resolve().parent

# SQLite 数据库文件路径
DB_PATH = BASE_DIR / "quant.db"

# 上传策略文件的保存目录（quant-platform/submissions/）
SUBMISSIONS_DIR = BASE_DIR.parent / "submissions"

# 下载中心资源目录（quant-platform/backend/downloads_assets/）
DOWNLOADS_DIR = BASE_DIR / "downloads_assets"

# 管理后台登录密码（教学演示用；生产环境请改为环境变量）
ADMIN_PASSWORD = "admin123"
