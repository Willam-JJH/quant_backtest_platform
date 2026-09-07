"""仪表盘路由。"""

from fastapi import APIRouter

from database import get_db

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard():
    """返回平台概览统计信息。"""
    with get_db() as conn:
        total_teams = conn.execute("SELECT COUNT(*) AS c FROM teams").fetchone()["c"]
        total_submissions = conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()["c"]
        # 最近 5 条提交
        recent = conn.execute(
            """SELECT s.id, t.display_name AS team_name, s.data_track, s.status, s.score, s.submitted_at
               FROM submissions s JOIN teams t ON s.team_id = t.id
               ORDER BY s.submitted_at DESC, s.id DESC LIMIT 5"""
        ).fetchall()
        # 每个轨道的最高分与成功提交数
        summary = conn.execute(
            """SELECT data_track, MAX(score) AS top_score, COUNT(*) AS count
               FROM submissions WHERE status = 'success'
               GROUP BY data_track ORDER BY data_track"""
        ).fetchall()
    return {
        "total_teams": total_teams,
        "total_submissions": total_submissions,
        "recent_submissions": [dict(r) for r in recent],
        "leaderboard_summary": [dict(r) for r in summary],
    }
