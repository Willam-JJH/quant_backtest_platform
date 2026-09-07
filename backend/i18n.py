"""后端返回文案的国际化：随请求语言返回中文或英文。

语言来源：请求头 X-Lang（"zh" 或 "en"，默认 "zh"，由前端统一附带）。
机制：ASGI 中间件把请求语言写入 ContextVar，_() 据此查翻译表；
未收录的文本或非 en 请求原样返回中文（中文原文即翻译表的 key）。

技术性错误内容（Python 语法报错、回测 traceback、底层异常 str）不在此列，
它们保持原文 —— 属于排错信息而非 UI 文案。
"""

from contextvars import ContextVar

# 当前请求语言（线程/协程隔离）
_LANG: ContextVar[str] = ContextVar("lang", default="zh")

# 英文翻译表：中文原文 → 英文；占位符用 {name}，由 _() 做替换。
_EN = {
    # ── 认证 / 会话 ──
    "未登录": "Not logged in",
    "登录已失效": "Session expired",
    "队名或密码错误": "Incorrect team name or password",
    "需要管理员登录": "Admin login required",
    "管理员登录已失效": "Admin session expired",
    "管理员密码错误": "Incorrect admin password",

    # ── 队伍 ──
    "队名已存在": "Team name already exists",
    "队伍不存在": "Team not found",

    # ── 提交 ──
    "非法数据轨道": "Invalid data track",
    "请上传 .py 文件": "Please upload a .py file",
    "请至少上传一个文件": "Please upload at least one file",
    "提交不存在": "Submission not found",
    "文件不存在": "File not found",
    "该提交未失败": "This submission did not fail",
    "缺少提交 id": "Missing submission id",
    "已重新排队，正在后台回测": "Re-queued — backtest is running in the background",
    "不支持的批量操作": "Unsupported bulk action",

    # ── 对比 ──
    "请提供两个提交 ID": "Please provide two submission IDs",
    "提交 {sid} 不存在": "Submission {sid} not found",
    "{team} / {track} / {score}分": "{team} / {track} / {score} pts",

    # ── 下载中心 ──
    "非法路径": "Invalid path",
    "文件暂未提供": "File is not available yet",
    "学习数据": "Learning Data",
    "策略模板": "Strategy Template",
    "快速开始指南": "Quick Start Guide",
    "课堂分发数据集打包（stock/basic/firm/market…）":
        "Classroom dataset bundle (stock / basic / firm / market…)",
    "包含 generate_signals 的标准策略骨架":
        "Standard strategy skeleton with generate_signals",
    "三步跑通首次提交": "Get your first submission working in 3 steps",
    "运行环境（{stem}）": "Runtime environment ({stem})",
    "本地回测运行环境打包": "Bundled local backtest runtime",

    # ── 真实 A 股因子回测 ──
    "真实数据包未接入：请在 datasource.DATA_SEARCH_PATHS 之一放置数据，或显式传入 data_dir。":
        "Real-market dataset is not connected: place data in one of "
        "datasource.DATA_SEARCH_PATHS, or pass a data_dir explicitly.",
    "数据或日期参数无效：{exc}": "Invalid data or date parameters: {exc}",
    "回测未能生成有效结果（数据可能不足）":
        "Backtest produced no valid results (data may be insufficient)",
}


def current_lang() -> str:
    """返回当前请求语言（"zh" / "en"）。"""
    return _LANG.get()


def _(text: str, **params) -> str:
    """按当前请求语言返回文案；支持 {name} 占位符替换。

    中文模式（或未收录的文本）原样返回 text —— text 本身即最终中文文案。
    """
    out = _EN.get(text, text) if _LANG.get() == "en" else text
    if params:
        for k, v in params.items():
            out = out.replace("{" + k + "}", str(v))
    return out


class LangMiddleware:
    """极薄 ASGI 中间件：解析 X-Lang 请求头并写入 ContextVar。

    用纯 ASGI 而非 FastAPI 依赖，确保在任何路由/鉴权依赖之前生效，
    且不依赖框架的依赖解析顺序。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        lang = "zh"
        for k, v in scope.get("headers") or ():
            if k == b"x-lang":
                val = v.decode("latin-1").strip().lower()
                if val in ("zh", "en"):
                    lang = val
                break

        token = _LANG.set(lang)
        try:
            await self.app(scope, receive, send)
        finally:
            _LANG.reset(token)
