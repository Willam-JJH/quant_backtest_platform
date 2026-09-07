"""SickFun 量化平台一键启动器。

一键拉起后端（FastAPI，含前端静态伺服）并用 ngrok 映射出公网域名：
    - 本地访问   http://localhost:8000
    - 公网域名   https://xxx.ngrok-free.app （自动获取并打印，浏览器输入即可进入）

用法：
    python start.py                # 正常启动（dist 缺失时自动 build 前端）
    python start.py --rebuild      # 强制重新 build 前端
    python start.py --no-build     # 跳过前端 build
    python start.py --no-ngrok     # 不启动 ngrok（仅本地访问）
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

# 控制台输出统一 UTF-8，避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent            # quant-platform/
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"

PORT = 8000
LOCAL_URL = f"http://localhost:{PORT}"
NGROK_API = "http://127.0.0.1:4040/api/tunnels"

# 固定域名：优先读环境变量 NGROK_DOMAIN，其次读根目录 ngrok-domain.txt
DOMAIN_FILE = ROOT.parent / "ngrok-domain.txt"

_children = []


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _kill(p):
    """终止子进程，尽力而为。"""
    if p and p.poll() is None:
        try:
            p.terminate()
        except Exception:
            return
        try:
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


def _cleanup():
    for p in _children:
        _kill(p)


atexit.register(_cleanup)


def _spawn(args, cwd=None):
    """后台启动子进程并登记，便于退出时清理。"""
    p = subprocess.Popen(
        args,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _children.append(p)
    return p


def _build_frontend(force=False):
    """构建前端静态产物；dist 存在且未强制时跳过。"""
    if DIST.is_dir() and (DIST / "index.html").exists() and not force:
        _log("前端 dist 已存在，跳过 build（--rebuild 可强制重建）")
        return True
    npm = shutil.which("npm")
    if not npm:
        _log("未找到 npm，跳过前端 build（将使用现有 dist，若缺失则前端 404）")
        return False
    _log("正在构建前端（npm run build）…")
    try:
        subprocess.run(
            [npm, "run", "build"],
            cwd=str(FRONTEND),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _log("前端构建完成")
        return True
    except subprocess.CalledProcessError:
        _log("前端构建失败（后端仍会启动，前端可能不可用）")
        return False


def _wait_backend(timeout=30.0):
    """轮询 /api/health 直到后端就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(LOCAL_URL + "/api/health", timeout=1.5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _resolve_domain():
    """解析固定域名：环境变量优先，其次 ngrok-domain.txt。"""
    domain = os.environ.get("NGROK_DOMAIN")
    if domain:
        return domain.strip()
    if DOMAIN_FILE.exists():
        text = DOMAIN_FILE.read_text(encoding="utf-8").strip()
        if text and not text.startswith("#"):
            return text.split()[0]
    return None


def _start_ngrok():
    """启动 ngrok，返回公网域名；失败返回 None。"""
    ngrok = shutil.which("ngrok")
    if not ngrok:
        _log("未找到 ngrok，跳过公网映射（仅本地访问）")
        return None

    cmd = [ngrok, "http", str(PORT)]

    domain = _resolve_domain()
    if domain:
        cmd += ["--domain", domain]
        _log(f"使用固定域名：{domain}")

    _log("正在启动 ngrok …")
    _spawn(cmd)

    # 轮询 ngrok 本地 API 拿公网地址
    deadline = time.time() + 30.0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(NGROK_API, timeout=1.5) as r:
                data = json.loads(r.read().decode())
                for t in data.get("tunnels", []):
                    if t.get("public_url"):
                        return t["public_url"]
        except Exception:
            pass
        time.sleep(0.8)
    _log("ngrok 未返回公网地址（可能未登录或网络异常）")
    return None


def main():
    args = sys.argv[1:]
    force_build = "--rebuild" in args
    no_build = "--no-build" in args
    no_ngrok = "--no-ngrok" in args

    print("=" * 56, flush=True)
    print("  SickFun 量化平台 · 一键启动", flush=True)
    print("=" * 56, flush=True)

    if not VENV_PYTHON.exists():
        _log(f"未找到 venv Python：{VENV_PYTHON}")
        _log("请先创建虚拟环境并安装依赖（见 backend/requirements.txt）")
        sys.exit(1)

    # 1. 构建前端
    if not no_build:
        _build_frontend(force=force_build)

    # 2. 启动后端
    _log("正在启动后端（FastAPI，端口 8000）…")
    backend = _spawn([str(VENV_PYTHON), "app.py"], cwd=BACKEND)

    if not _wait_backend():
        _log("后端启动失败或超时，请检查 backend 是否正常")
        _cleanup()
        sys.exit(1)
    # 确认是我们启动的进程在服务（排除上次残留进程占用端口导致的假就绪）
    time.sleep(0.5)
    if backend.poll() is not None:
        _log("后端进程意外退出——端口 8000 可能被上次残留的进程占用")
        _log("请在任务管理器结束残留的 python.exe 后重试")
        _cleanup()
        sys.exit(1)
    _log("后端已就绪")

    # 3. 启动 ngrok 并获取公网域名
    public_url = None
    if not no_ngrok:
        public_url = _start_ngrok()

    # 4. 打印访问地址并打开浏览器
    print("=" * 56, flush=True)
    print(f"  本地地址  : {LOCAL_URL}", flush=True)
    if public_url:
        print(f"  公网域名  : {public_url}", flush=True)
        print("  → 浏览器输入上面的公网域名即可进入（任何人可访问）", flush=True)
    else:
        print("  → 未启用公网映射，仅本机可访问", flush=True)
    print("  按 Ctrl+C 停止服务", flush=True)
    print("=" * 56, flush=True)

    try:
        webbrowser.open(public_url or LOCAL_URL)
    except Exception:
        pass

    # 5. 挂起，直到用户中断或后端退出
    try:
        while backend.poll() is None:
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        _log("正在停止服务…")
        _cleanup()
        _log("已退出")


if __name__ == "__main__":
    main()
