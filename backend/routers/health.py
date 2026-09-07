"""健康检查路由。"""

from fastapi import APIRouter

# 创建路由实例，统一使用 /api 前缀
router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check():
    """返回服务健康状态，用于验证后端是否正常运行。"""
    return {"app": "QuantPlatform", "status": "ok"}
