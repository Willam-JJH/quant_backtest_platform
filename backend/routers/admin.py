"""管理后台路由。"""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from backtest_engine import start_backtest
from config import ADMIN_PASSWORD, SUBMISSIONS_DIR
from database import get_db
from i18n import _

router = APIRouter(prefix="/api/admin", tags=["admin"])

# 管理员 session 存储（教学演示：进程内存）
_admin_tokens = {}


class AdminLogin(BaseModel):
    password: str


class CreateTeam(BaseModel):
    name: str
    display_name: str
    password: str


class BulkAction(BaseModel):
    action: str  # delete / create_sample 等
    ids: list[int] = []


def _require_admin(authorization: str = Header(default=None)):
    """管理员鉴权依赖。"""
    if not authorization:
        raise HTTPException(status_code=401, detail=_("需要管理员登录"))
    token = authorization.replace("Bearer ", "").strip()
    if _admin_tokens.get(token) != "admin":
        raise HTTPException(status_code=401, detail=_("管理员登录已失效"))
    return True


@router.post("/login")
def admin_login(req: AdminLogin):
    """管理员登录。"""
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail=_("管理员密码错误"))
    token = uuid.uuid4().hex
    _admin_tokens[token] = "admin"
    return {"token": token}


# ───────────── 队伍管理 ─────────────

@router.get("/teams", dependencies=[Depends(_require_admin)])
def admin_list_teams():
    """所有队伍列表（含提交次数）。"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT t.id, t.name, t.display_name, t.created_at,
                      (SELECT COUNT(*) FROM submissions s WHERE s.team_id = t.id) AS submission_count
               FROM teams t ORDER BY t.id"""
        ).fetchall()
    return {"rows": [dict(r) for r in rows]}


@router.post("/teams", dependencies=[Depends(_require_admin)])
def admin_create_team(req: CreateTeam):
    """创建队伍。"""
    with get_db() as conn:
        exists = conn.execute("SELECT id FROM teams WHERE name = ?", (req.name,)).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail=_("队名已存在"))
        cur = conn.execute(
            "INSERT INTO teams (name, display_name, password) VALUES (?, ?, ?)",
            (req.name, req.display_name, req.password),
        )
        team_id = cur.lastrowid
    return {"id": team_id, "name": req.name, "display_name": req.display_name}


@router.delete("/teams/{team_id}", dependencies=[Depends(_require_admin)])
def admin_delete_team(team_id: int):
    """删除队伍：连带删除其提交记录与上传文件。"""
    _delete_team_records(team_id)
    return {"success": True}


@router.post("/teams/bulk-action", dependencies=[Depends(_require_admin)])
def admin_teams_bulk(req: BulkAction):
    """队伍批量操作。当前支持 delete。"""
    if req.action != "delete":
        raise HTTPException(status_code=400, detail=_("不支持的批量操作"))
    for tid in req.ids:
        _delete_team_records(tid)
    return {"success": True, "deleted": req.ids}


def _delete_team_records(team_id: int):
    """删除队伍及其提交与文件。"""
    with get_db() as conn:
        subs = conn.execute(
            "SELECT file_path FROM submissions WHERE team_id = ?", (team_id,)
        ).fetchall()
        for s in subs:
            try:
                Path(s["file_path"]).unlink(missing_ok=True)
            except OSError:
                pass
        conn.execute("DELETE FROM submissions WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    # 清空上传目录
    shutil.rmtree(SUBMISSIONS_DIR / str(team_id), ignore_errors=True)


# ───────────── 提交管理 ─────────────

@router.get("/submissions", dependencies=[Depends(_require_admin)])
def admin_list_submissions(limit: int = 100, offset: int = 0):
    """所有提交列表。"""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()["c"]
        rows = conn.execute(
            """SELECT s.*, t.name AS team_name, t.display_name AS team_display_name
               FROM submissions s JOIN teams t ON s.team_id = t.id
               ORDER BY s.id DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    return {
        "rows": [dict(r) for r in rows],
        "count": len(rows),
        "total_count": total,
    }


@router.delete("/submissions/{submission_id}", dependencies=[Depends(_require_admin)])
def admin_delete_submission(submission_id: int):
    """删除提交记录及其文件。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT file_path FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=_("提交不存在"))
        try:
            Path(row["file_path"]).unlink(missing_ok=True)
        except OSError:
            pass
        conn.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
    return {"success": True}


@router.post("/submissions/rerun", dependencies=[Depends(_require_admin)])
def admin_rerun_submission(payload: dict):
    """重新运行提交：状态置回 pending 并启动后台回测。"""
    sid = payload.get("id")
    if not sid:
        raise HTTPException(status_code=400, detail=_("缺少提交 id"))
    with get_db() as conn:
        row = conn.execute("SELECT id FROM submissions WHERE id = ?", (sid,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=_("提交不存在"))
        conn.execute(
            "UPDATE submissions SET status='pending', score=NULL, metrics=NULL, "
            "error_message=NULL, scored_at=NULL WHERE id = ?",
            (sid,),
        )
    start_backtest(sid)
    return {"success": True, "message": _("已重新排队，正在后台回测")}


# ───────────── 平台设置 / 统计 ─────────────

@router.get("/settings", dependencies=[Depends(_require_admin)])
def admin_settings():
    """平台配置与统计信息。"""
    with get_db() as conn:
        total_teams = conn.execute("SELECT COUNT(*) AS c FROM teams").fetchone()["c"]
        total_sub = conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()["c"]
        by_track = conn.execute(
            "SELECT data_track, status, COUNT(*) AS c FROM submissions GROUP BY data_track, status ORDER BY data_track"
        ).fetchall()
    return {
        "app": "QuantPlatform",
        "version": "0.1.0",
        "data_tracks": ["learning_1", "learning_2", "learning_3", "hidden"],
        "stats": {
            "total_teams": total_teams,
            "total_submissions": total_sub,
        },
        "by_track_status": [dict(r) for r in by_track],
    }
