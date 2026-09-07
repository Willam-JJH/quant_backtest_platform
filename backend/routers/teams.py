"""队伍管理路由。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db
from i18n import _

router = APIRouter(prefix="/api", tags=["teams"])


class RegisterRequest(BaseModel):
    """注册请求体。"""
    name: str
    display_name: str
    password: str


@router.post("/teams/register")
def register(req: RegisterRequest):
    """创建新队伍，返回队伍信息（不含密码）。"""
    with get_db() as conn:
        exists = conn.execute("SELECT id FROM teams WHERE name = ?", (req.name,)).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail=_("队名已存在"))
        cur = conn.execute(
            "INSERT INTO teams (name, display_name, password) VALUES (?, ?, ?)",
            (req.name, req.display_name, req.password),
        )
        row = conn.execute(
            "SELECT id, name, display_name, created_at FROM teams WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return dict(row)


@router.get("/teams")
def list_teams(limit: int = 20, offset: int = 0):
    """返回队伍列表（分页）。"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, display_name, created_at FROM teams ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM teams").fetchone()["c"]
    return {
        "rows": [dict(r) for r in rows],
        "count": len(rows),
        "total_count": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + len(rows) < total,
    }


@router.get("/teams/{team_id}")
def get_team(team_id: int):
    """返回单个队伍详情，包含提交次数。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, display_name, created_at FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=_("队伍不存在"))
        sub_count = conn.execute(
            "SELECT COUNT(*) AS c FROM submissions WHERE team_id = ?", (team_id,)
        ).fetchone()["c"]
    result = dict(row)
    result["submission_count"] = sub_count
    return result
