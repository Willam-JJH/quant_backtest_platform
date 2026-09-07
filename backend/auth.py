"""认证/登录辅助逻辑。"""

import uuid

from fastapi import Header, HTTPException

from database import get_db
from i18n import _

# 内存 session 存储：token -> team_id（教学用，重启即失效）
_sessions = {}


def create_session(team_id: int) -> str:
    """为队伍创建 session，返回 token。"""
    token = uuid.uuid4().hex
    _sessions[token] = team_id
    return token


def get_current_team(token: str):
    """根据 token 返回队伍信息，无效则返回 None。"""
    team_id = _sessions.get(token)
    if team_id is None:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, display_name FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
    return dict(row) if row else None


def destroy_session(token: str):
    """清除指定 session。"""
    _sessions.pop(token, None)


def require_auth(authorization: str = Header(default=None)):
    """FastAPI 依赖注入函数：校验 token，返回队伍信息，失败抛 401。

    前端通过 `Authorization: Bearer <token>` 请求头传入 token。
    """
    if not authorization:
        raise HTTPException(status_code=401, detail=_("未登录"))
    token = authorization.replace("Bearer ", "").strip()
    team = get_current_team(token)
    if team is None:
        raise HTTPException(status_code=401, detail=_("登录已失效"))
    return team
