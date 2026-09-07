"""下载中心路由。"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import DOWNLOADS_DIR
from i18n import _

router = APIRouter(prefix="/api", tags=["downloads"])


def _file_size(path: Path) -> int:
    """返回文件字节数，不存在返回 0。"""
    try:
        return path.stat().st_size
    except OSError:
        return 0


@router.get("/downloads")
def downloads_manifest():
    """返回可下载资源清单（名称 / 说明 / 是否可用 / 大小）。"""
    env_dir = DOWNLOADS_DIR / "environment"

    # 固定条目：learning-data 存在与否决定是否可用
    learning_zip = DOWNLOADS_DIR / "learning-data.zip"
    starter = DOWNLOADS_DIR / "starter-strategy.py"
    quickstart = DOWNLOADS_DIR / "quickstart.txt"

    items = [
        {
            "key": "learning-data",
            "name": _("学习数据"),
            "desc": _("课堂分发数据集打包（stock/basic/firm/market…）"),
            "filename": "learning-data.zip",
            "available": learning_zip.exists(),
            "size": _file_size(learning_zip),
        },
        {
            "key": "starter",
            "name": _("策略模板"),
            "desc": _("包含 generate_signals 的标准策略骨架"),
            "filename": "starter-strategy.py",
            "available": starter.exists(),
            "size": _file_size(starter),
        },
        {
            "key": "quickstart",
            "name": _("快速开始指南"),
            "desc": _("三步跑通首次提交"),
            "filename": "quickstart.txt",
            "available": quickstart.exists(),
            "size": _file_size(quickstart),
        },
    ]

    # 运行环境包：扫描 environment/ 目录下的 *.zip
    environments = []
    if env_dir.is_dir():
        for f in sorted(env_dir.glob("*.zip")):
            environments.append(
                {
                    "key": f"env-{f.stem}",
                    "name": _("运行环境（{stem}）", stem=f.stem),
                    "desc": _("本地回测运行环境打包"),
                    "filename": f"environment/{f.name}",
                    "available": True,
                    "size": f.stat().st_size,
                }
            )
    return {"items": items + environments}


@router.get("/downloads/environment-options")
def environment_options():
    """可用运行环境平台列表。"""
    env_dir = DOWNLOADS_DIR / "environment"
    platforms = []
    if env_dir.is_dir():
        platforms = [f.stem for f in env_dir.glob("*.zip")]
    return {"platforms": platforms}


def _send(filename: str):
    """按文件名返回文件，不存在则 404。"""
    path = DOWNLOADS_DIR / filename
    # 防止路径穿越
    try:
        path.relative_to(DOWNLOADS_DIR)
    except ValueError:
        raise HTTPException(status_code=400, detail=_("非法路径"))
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=_("文件暂未提供"))
    return FileResponse(path, filename=path.name)


@router.get("/downloads/{filename:path}")
def download(filename: str):
    """下载指定资源文件（starter-strategy.py / quickstart.txt / learning-data.zip / environment/*.zip）。"""
    # 归一化路径：environment/xxx.zip 也在资源目录下
    return _send(filename)
