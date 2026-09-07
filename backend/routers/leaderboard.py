"""排行榜路由。"""

import json

from fastapi import APIRouter

from database import get_db

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard")
def get_leaderboard(data_track: str = None, limit: int = 20, offset: int = 0):
    """返回排行榜：每个队伍每个轨道只取分数最高的一条，按分数降序，处理并列。

    - 可选 data_track 参数筛选轨道
    - RANK() 处理并列：分数相同则名次相同
    """
    conditions = ["s.status = 'success'"]
    params = []
    if data_track is not None:
        conditions.append("s.data_track = ?")
        params.append(data_track)
    where = " AND ".join(conditions)

    # 内层：每个队伍每个轨道只保留分数最高（相同分数取最新）的一条
    inner = f"""
        SELECT s.id AS submission_id, s.team_id, s.data_track, s.score, s.metrics,
               s.submitted_at, t.name AS team_name, t.display_name AS team_display_name,
               ROW_NUMBER() OVER (
                   PARTITION BY s.team_id, s.data_track
                   ORDER BY s.score DESC, s.submitted_at DESC
               ) AS rn
        FROM submissions s JOIN teams t ON s.team_id = t.id
        WHERE {where}
    """
    with get_db() as conn:
        # 去重后的总条数
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM ({inner}) WHERE rn = 1", params
        ).fetchone()["c"]
        # 对去重结果计算全局排名（RANK 处理并列）后分页
        rows = conn.execute(
            f"""
            SELECT submission_id, team_id, data_track, score, metrics, submitted_at,
                   team_name, team_display_name,
                   RANK() OVER (ORDER BY score DESC) AS rank
            FROM ({inner})
            WHERE rn = 1
            ORDER BY score DESC, submission_id ASC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

    result_rows = []
    for r in rows:
        d = dict(r)
        # metrics 为 JSON 字符串，解析成对象
        if d.get("metrics"):
            try:
                d["metrics"] = json.loads(d["metrics"])
            except Exception:
                pass
        result_rows.append(d)

    return {
        "rows": result_rows,
        "count": len(result_rows),
        "total_count": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + len(result_rows) < total,
    }
