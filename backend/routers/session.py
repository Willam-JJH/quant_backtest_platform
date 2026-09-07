"""登录/登出路由。"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from auth import create_session, destroy_session, require_auth
from database import get_db
from i18n import _

router = APIRouter(prefix="/api", tags=["session"])


class LoginRequest(BaseModel):
    """登录请求体。"""
    name: str
    password: str


@router.post("/session/login")
def login(req: LoginRequest):
    """队伍登录：验证密码，创建 session 并返回 token。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, display_name, password FROM teams WHERE name = ?",
            (req.name,),
        ).fetchone()
    if row is None or row["password"] != req.password:
        raise HTTPException(status_code=401, detail=_("队名或密码错误"))
    token = create_session(row["id"])
    return {
        "team": {"id": row["id"], "name": row["name"], "display_name": row["display_name"]},
        "token": token,
    }


@router.get("/session")
def current_session(team=Depends(require_auth)):
    """返回当前登录队伍信息。"""
    return {"team": team}


@router.post("/session/logout")
def logout(authorization: str = Header(default=None)):
    """登出，清除 session。"""
    if authorization:
        destroy_session(authorization.replace("Bearer ", "").strip())
    return {"success": True}
