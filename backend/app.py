"""量化平台 FastAPI 主应用入口。

启动方式：
    cd backend && python app.py
    访问 http://127.0.0.1:8000/api/health
"""

import uvicorn
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from routers import (
    health, session, teams, submissions, leaderboard,
    dashboard, compare, downloads, admin,
    factor_backtest,  # 真实 A 股因子回测路由
)
from database import init_db  # 数据库初始化
from i18n import LangMiddleware  # 请求语言 → 后端文案本地化

# 创建 FastAPI 应用实例
app = FastAPI(title="QuantPlatform", description="SickFun 量化平台后端")

# 解析请求语言（X-Lang），供 _() 按语言返回文案
app.add_middleware(LangMiddleware)

# 启动时初始化数据库（创建数据表）
init_db()

# 添加 CORS 中间件，允许所有来源（开发阶段）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],   # 允许所有 HTTP 方法
    allow_headers=["*"],   # 允许所有请求头
)

# 注册各功能路由
app.include_router(health.router)
app.include_router(session.router)
app.include_router(teams.router)
app.include_router(submissions.router)
app.include_router(leaderboard.router)
app.include_router(dashboard.router)
app.include_router(compare.router)
app.include_router(downloads.router)
app.include_router(admin.router)
app.include_router(factor_backtest.router)


# ───────────── 前端静态文件伺服（一键启动 / 生产模式）─────────────
# 前端 build 产物 frontend/dist 由后端同源伺服，整个站点只占一个端口：
#   /api/*      → 上面的 API 路由
#   /assets/*   → 打包出的 js/css 静态资源
#   其余路径     → 回退 index.html（支持 React Router 前端路由）
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _serve_frontend(full_path: str):
        # API 未命中的路径不当作前端路由处理，交给默认 404
        if full_path.startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    # 启动开发服务器（127.0.0.1:8000）
    uvicorn.run(app, host="127.0.0.1", port=8000)
