"""策略提交路由。"""

import json
import os
import py_compile
import re
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse

from backtest_engine import start_backtest
from config import SUBMISSIONS_DIR
from database import get_db
from models import DataTrack
from i18n import _

router = APIRouter(prefix="/api", tags=["submissions"])

# 合法的数据轨道集合
VALID_TRACKS = [t.value for t in DataTrack]


async def _save_submission(team_id: int, data_track: str, file: UploadFile) -> dict:
    """保存单个策略文件并创建 pending 记录，返回 submission 行（dict）。"""
    # b. 验证 data_track 合法
    if data_track not in VALID_TRACKS:
        raise HTTPException(status_code=400, detail=_("非法数据轨道"))
    # c. 验证文件是 .py 后缀
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail=_("请上传 .py 文件"))

    with get_db() as conn:
        # a. 验证 team_id 存在
        team = conn.execute("SELECT id FROM teams WHERE id = ?", (team_id,)).fetchone()
        if team is None:
            raise HTTPException(status_code=404, detail=_("队伍不存在"))

        # d. 保存文件到 submissions/{team_id}/{timestamp}_{filename}
        team_dir = SUBMISSIONS_DIR / str(team_id)
        team_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = Path(file.filename).name  # 去掉路径部分，防止目录穿越
        dest = team_dir / f"{timestamp}_{safe_name}"
        content = await file.read()
        dest.write_bytes(content)

        # e. 创建 submission 记录，status='pending'
        cur = conn.execute(
            "INSERT INTO submissions (team_id, data_track, status, file_path) "
            "VALUES (?, ?, 'pending', ?)",
            (team_id, data_track, str(dest)),
        )
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


@router.post("/submissions")
async def create_submission(
    team_id: int = Form(...),
    data_track: str = Form(...),
    file: UploadFile = File(...),
):
    """接收策略文件，保存到磁盘并创建提交记录（status='pending'）。"""
    row = await _save_submission(team_id, data_track, file)
    # f. 提交成功后启动后台线程执行回测
    start_backtest(row["id"])
    # g. 返回创建的 submission 对象
    return row


@router.post("/submissions/batch")
async def create_submission_batch(
    team_id: int = Form(...),
    data_track: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """批量接收多个策略文件，逐个保存并进入评分队列。

    返回 {"created": [id, ...], "count": n}。放在 /submissions/{id} 之前，
    避免 "batch" 被 int 路径参数吞掉。
    """
    if not files:
        raise HTTPException(status_code=400, detail=_("请至少上传一个文件"))
    created = []
    for f in files:
        row = await _save_submission(team_id, data_track, f)
        start_backtest(row["id"])
        created.append(row["id"])
    return {"created": created, "count": len(created)}


@router.get("/submissions")
def list_submissions(
    team_id: int = None,
    data_track: str = None,
    status: str = None,
    limit: int = 20,
    offset: int = 0,
):
    """返回提交列表（按时间倒序），支持筛选与分页，每条含队伍名。"""
    conditions = []
    params = []
    if team_id is not None:
        conditions.append("s.team_id = ?")
        params.append(team_id)
    if data_track is not None:
        conditions.append("s.data_track = ?")
        params.append(data_track)
    if status is not None:
        conditions.append("s.status = ?")
        params.append(status)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM submissions s{where}", params
        ).fetchone()["c"]
        rows = conn.execute(
            f"""SELECT s.*, t.name AS team_name, t.display_name AS team_display_name
                FROM submissions s JOIN teams t ON s.team_id = t.id
                {where}
                ORDER BY s.submitted_at DESC, s.id DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()
    return {
        "rows": [dict(r) for r in rows],
        "count": len(rows),
        "total_count": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + len(rows) < total,
    }


@router.get("/submissions/options")
def submission_options():
    """返回可用的数据轨道列表。"""
    return {"data_tracks": VALID_TRACKS}


@router.post("/submissions/check")
async def check_python(request: Request):
    """对纯文本源码做 Python 语法预检查（py_compile）。

    请求体为源码原文（text/plain），返回 {"errors": [{"line": n, "msg": "..."}]}，
    无语法错误时 errors 为空列表。放在 /submissions/{id} 之前，避免被 int 路径参数吞掉。
    """
    code = (await request.body()).decode("utf-8")
    if not code.strip():
        return {"errors": []}

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name
        py_compile.compile(tmp_path, doraise=True)
        return {"errors": []}
    except py_compile.PyCompileError as exc:
        msg = str(exc)
        m = re.search(r"line (\d+)", msg)
        line = int(m.group(1)) if m else 0
        return {"errors": [{"line": line, "msg": msg}]}
    except Exception as exc:  # noqa: BLE001
        return {"errors": [{"line": 0, "msg": str(exc)}]}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: int):
    """返回单个提交的详细信息。"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT s.*, t.name AS team_name, t.display_name AS team_display_name
               FROM submissions s JOIN teams t ON s.team_id = t.id
               WHERE s.id = ?""",
            (submission_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=_("提交不存在"))
    result = dict(row)
    # metrics 为 JSON 字符串，解析成对象返回
    if result.get("metrics"):
        try:
            result["metrics"] = json.loads(result["metrics"])
        except Exception:
            pass
    # file_path 仅返回文件名，不暴露全路径
    if result.get("file_path"):
        result["file_path"] = Path(result["file_path"]).name
    return result


@router.get("/submissions/{submission_id}/source")
def get_source(submission_id: int):
    """返回提交的策略文件源代码（文本格式）。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT file_path FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=_("提交不存在"))
    path = Path(row["file_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail=_("文件不存在"))
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.get("/submissions/{submission_id}/raw-error")
def get_raw_error(submission_id: int):
    """返回原始错误信息（仅当 status=failed）。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT status, error_message FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=_("提交不存在"))
    if row["status"] != "failed":
        raise HTTPException(status_code=400, detail=_("该提交未失败"))
    return PlainTextResponse(row["error_message"] or "")
