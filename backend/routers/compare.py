"""策略对比路由。"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db
from i18n import _

router = APIRouter(prefix="/api", tags=["compare"])


class CompareRequest(BaseModel):
    """对比请求体。"""
    submission_ids: list[int]


@router.post("/compare")
def compare(req: CompareRequest):
    """返回两个提交的详细指标对比与差值。"""
    ids = req.submission_ids
    if len(ids) != 2:
        raise HTTPException(status_code=400, detail=_("请提供两个提交 ID"))

    with get_db() as conn:
        rows = []
        for sid in ids:
            r = conn.execute(
                """SELECT s.id, s.score, s.metrics, s.data_track,
                          t.name AS team_name, t.display_name AS team_display_name
                   FROM submissions s JOIN teams t ON s.team_id = t.id
                   WHERE s.id = ?""",
                (sid,),
            ).fetchone()
            if r is None:
                raise HTTPException(status_code=404, detail=_("提交 {sid} 不存在", sid=sid))
            d = dict(r)
            if d.get("metrics"):
                try:
                    d["metrics"] = json.loads(d["metrics"])
                except Exception:
                    pass
            rows.append(d)

    # 计算差值（第一个减第二个）
    a, b = rows[0], rows[1]
    deltas = {}
    if a.get("score") is not None and b.get("score") is not None:
        deltas["score"] = round(a["score"] - b["score"], 4)
    ma = a.get("metrics") or {}
    mb = b.get("metrics") or {}
    for key in set(ma) | set(mb):
        va, vb = ma.get(key), mb.get(key)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            deltas[key] = round(va - vb, 6)

    return {"submissions": rows, "deltas": deltas}


@router.get("/compare/options")
def compare_options():
    """返回可用于对比的提交列表（每个队伍每个轨道取最佳）。"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, score, data_track, team_display_name FROM (
                   SELECT s.id, s.score, s.data_track, t.display_name AS team_display_name,
                          ROW_NUMBER() OVER (
                              PARTITION BY s.team_id, s.data_track
                              ORDER BY s.score DESC, s.submitted_at DESC
                          ) AS rn
                   FROM submissions s JOIN teams t ON s.team_id = t.id
                   WHERE s.status = 'success'
               ) WHERE rn = 1 ORDER BY score DESC"""
        ).fetchall()
    options = [
        {
            "id": r["id"],
            "label": _(
                "{team} / {track} / {score}分",
                team=r["team_display_name"],
                track=r["data_track"],
                score=r["score"],
            ),
        }
        for r in rows
    ]
    return {"submissions": options}
