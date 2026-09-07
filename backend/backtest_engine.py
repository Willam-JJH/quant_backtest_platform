"""回测引擎（Bonus 部分）。

流程：
    1. 从数据库读取 submission 记录
    2. 动态导入策略文件，取 generate_signals(data, date) 函数
    3. 按轨道固定随机种子生成模拟市场数据（保证排行榜可比）
    4. 逐日调用策略得到信号，按信号分 5 组，做多空组合
    5. 计算评分指标并回写 submissions 表

评分（0-100）：
    score = annual_return_normalized*0.4 + sharpe_normalized*0.3 + (1-|max_drawdown|)*0.3
"""

import importlib.util
import json
import math
import random
import threading
import traceback
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from config import SUBMISSIONS_DIR  # noqa: F401  (保留引用，便于定位上传目录)
from database import get_db

# 每轨道的固定随机种子：同一轨道所有提交在相同模拟数据上评分，分数可比
TRACK_SEEDS = {
    "learning_1": 101,
    "learning_2": 102,
    "learning_3": 103,
    "hidden": 104,
}

# 回测参数
N_STOCKS = 50            # 模拟股票数量
N_DAYS = 252             # 模拟交易日数量（约一年）
LOOKBACK = 20            # 策略所需的最少历史天数
N_GROUPS = 5             # 信号分组数（分位分组）
TRADING_DAYS = 252       # 年化用的交易日数


# ───────────────────────── 工具函数 ─────────────────────────

def _safe_float(v):
    """把任意值转成有限 float；NaN/Inf/不可转 → 0.0。"""
    try:
        f = float(v)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_signal_map(signal, codes):
    """把策略返回的信号统一成 {code: float}。

    兼容 pandas.Series / dict / list / ndarray / 标量。
    """
    if signal is None:
        return {c: 0.0 for c in codes}
    # Mapping 类型（pd.Series、dict 等）：按 code 取值
    if hasattr(signal, "items"):
        out = {str(c): _safe_float(v) for c, v in signal.items()}
        for c in codes:
            out.setdefault(c, 0.0)
        return out
    # 标量：广播到所有股票
    if isinstance(signal, (int, float)):
        v = _safe_float(signal)
        return {c: v for c in codes}
    # 序列（list/tuple/ndarray）：按顺序对齐
    try:
        seq = list(signal)
    except TypeError:
        return {c: 0.0 for c in codes}
    out = {}
    for i, c in enumerate(codes):
        out[c] = _safe_float(seq[i]) if i < len(seq) else 0.0
    return out


# ───────────────────────── 模拟市场数据 ─────────────────────────

def _generate_market(data_track):
    """按轨道固定种子生成模拟市场数据。

    返回 SimpleNamespace：
        hist    — pandas.DataFrame，含 date/code/close/amount 列
        codes   — 股票代码列表
        dates   — 交易日列表（'YYYY-MM-DD' 字符串）
        closes  — {code: [逐日收盘价]}
        amounts — {code: [逐日成交额]}
    """
    seed = TRACK_SEEDS.get(data_track, 100)
    rng = random.Random(seed)
    dates = pd.bdate_range("2025-01-02", periods=N_DAYS)
    codes = [f"S{i:03d}" for i in range(N_STOCKS)]

    closes = {c: [] for c in codes}
    amounts = {c: [] for c in codes}
    for c in codes:
        price = rng.uniform(20.0, 200.0)
        base_amt = rng.uniform(1e6, 1e7)
        for _ in range(N_DAYS):
            # 几何随机游走，日波动约 2%
            price *= math.exp(rng.gauss(0.0, 0.02))
            closes[c].append(price)
            amounts[c].append(base_amt * rng.uniform(0.5, 1.5))

    # 构成长表 DataFrame（date 慢变，code 快变）
    date_col, code_col, close_col, amount_col = [], [], [], []
    for t, d in enumerate(dates):
        for c in codes:
            date_col.append(d)
            code_col.append(c)
            close_col.append(closes[c][t])
            amount_col.append(amounts[c][t])
    hist = pd.DataFrame(
        {"date": date_col, "code": code_col, "close": close_col, "amount": amount_col}
    )

    return SimpleNamespace(
        hist=hist,
        codes=codes,
        dates=[d.strftime("%Y-%m-%d") for d in dates],
        closes=closes,
        amounts=amounts,
    )


# ───────────────────────── 策略加载 ─────────────────────────

def _load_strategy(path):
    """动态导入策略文件，返回其模块对象。"""
    spec = importlib.util.spec_from_file_location("user_strategy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "generate_signals"):
        raise ValueError("策略文件缺少 generate_signals(data, date) 函数")
    return module


# ───────────────────────── 回测 ─────────────────────────

def _run_strategy_backtest(strategy, data):
    """逐日调用策略，按信号分 5 组做多空组合。

    返回 (daily, avg_signal)：
        daily      — [(date, 多空日收益), ...]
        avg_signal — {code: 全周期平均信号}（用于个股打分与 Top/Bottom 名单）
    """
    closes = data.closes
    amounts = data.amounts
    codes = data.codes
    n = N_DAYS
    daily = []
    sig_sum = {c: 0.0 for c in codes}
    n_rebalance = 0
    group_series = {f"G{i+1}": [] for i in range(N_GROUPS)}

    for t in range(LOOKBACK, n):
        date = data.dates[t]
        # 1. 取当日信号，并累积用于个股打分
        signal = strategy.generate_signals(data, date)
        sig_map = _to_signal_map(signal, codes)
        for c in codes:
            sig_sum[c] += sig_map.get(c, 0.0)
        n_rebalance += 1

        # 2. 当日每只股票收益 + 成交额
        ret = {}
        for c in codes:
            prev = closes[c][t - 1]
            cur = closes[c][t]
            ret[c] = (cur / prev - 1.0) if prev else 0.0

        # 3. 按信号升序排列，分 N_GROUPS 组（分位）
        ranked = sorted(codes, key=lambda c: sig_map.get(c, 0.0))
        k = N_GROUPS
        groups = [[] for _ in range(k)]
        for i, c in enumerate(ranked):
            g = min(int(i * k / len(ranked)), k - 1)
            groups[g].append(c)

        def group_ret(members):
            """成交额加权的组内收益。"""
            num = 0.0
            den = 0.0
            for c in members:
                w = amounts[c][t]
                num += w * ret[c]
                den += w
            return num / den if den else 0.0

        # 4. 计算各组收益（供分组曲线）并做多空组合
        group_rets = [group_ret(g) for g in groups]
        for i, gr in enumerate(group_rets):
            group_series[f"G{i+1}"].append(gr)
        top = group_rets[-1]    # 信号最高分组
        bottom = group_rets[0]  # 信号最低分组
        daily.append((date, top - bottom))

    if n_rebalance:
        avg_signal = {c: sig_sum[c] / n_rebalance for c in codes}
    else:
        avg_signal = {c: 0.0 for c in codes}
    return daily, avg_signal, group_series


# ───────────────────────── 指标与评分 ─────────────────────────

def _compute_metrics(daily):
    """由日收益序列计算全部评分指标。"""
    if not daily:
        raise ValueError("回测窗口为空，无法计算指标")

    dates = [d for d, _ in daily]
    rets = [r for _, r in daily]
    n = len(rets)

    # 累计收益曲线（复利），values[i] = 第 i 天结束时的累计收益
    eq = 1.0
    cum_values = []
    for r in rets:
        eq *= (1.0 + r)
        cum_values.append(eq - 1.0)
    cumulative_return = eq - 1.0

    # 年化收益
    annual_return = (1.0 + cumulative_return) ** (TRADING_DAYS / n) - 1.0

    # 均值 / 标准差
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / n
    std = math.sqrt(var)
    daily_std = std
    volatility = std * math.sqrt(TRADING_DAYS)
    sharpe = (mean / std * math.sqrt(TRADING_DAYS)) if std > 0 else 0.0

    # 最大回撤（正值，如 0.15 表示 -15%）
    peak = 0.0
    max_dd = 0.0
    for v in cum_values:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)

    # 胜率
    win_rate = sum(1 for r in rets if r > 0) / n

    return {
        "annual_return": annual_return,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "volatility": volatility,
        "win_rate": win_rate,
        "cumulative_return": cumulative_return,
        "daily_std": daily_std,
        "curve": {"dates": dates, "values": cum_values},
    }


def _score(metrics):
    """综合评分（0-100）。对年化收益与夏普做 sigmoid 归一，回撤项直接线性。"""
    annual_return = metrics["annual_return"]
    sharpe = metrics["sharpe"]
    max_dd = metrics["max_drawdown"]

    def sigmoid(x):
        return 1.0 / (1.0 + math.exp(-x))

    ar_norm = sigmoid(annual_return / 0.25)   # 0 收益 → 0.5
    sh_norm = sigmoid(sharpe / 1.0)           # 0 夏普 → 0.5
    dd_term = 1.0 - min(1.0, abs(max_dd))     # [0, 1]

    score = (ar_norm * 0.4 + sh_norm * 0.3 + dd_term * 0.3) * 100.0
    return round(score, 2)


def _compute_stocks(avg_signal, top_n=10):
    """由个股平均信号生成多空候选名单。

    返回：
        top    — 信号最高的 top_n 只（多头候选）
        bottom — 信号最低的 top_n 只（空头候选）
        all    — 全部股票按信号降序（供 score 分布直方图使用）
    """
    ranked = sorted(avg_signal.items(), key=lambda kv: kv[1], reverse=True)

    def fmt(pairs):
        return [{"code": c, "score": round(v, 6)} for c, v in pairs]

    return {
        "top": fmt(ranked[:top_n]),
        "bottom": fmt(ranked[-top_n:][::-1]),
        "all": fmt(ranked),
    }


def _compute_groups(group_series, dates):
    """由各组日收益序列生成累计收益曲线（供分组曲线图）。"""
    series = {}
    for gname, rets in group_series.items():
        eq = 1.0
        cum = []
        for r in rets:
            eq *= (1.0 + r)
            cum.append(eq - 1.0)
        series[gname] = cum
    return {"dates": dates, "series": series}


def _compute_daily_pnl(daily):
    """由组合多空日收益生成每日盈亏序列（正盈负亏，供柱状图）。"""
    return {
        "dates": [d for d, _ in daily],
        "values": [r for _, r in daily],
    }


# ───────────────────────── 主流程 ─────────────────────────

def run_backtest(submission_id):
    """对指定 submission 执行回测，并回写 success/failed 结果。"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            return
        file_path = row["file_path"]
        data_track = row["data_track"]

    try:
        # 标记运行中
        with get_db() as conn:
            conn.execute(
                "UPDATE submissions SET status='running' WHERE id=?", (submission_id,)
            )

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"策略文件不存在：{path}")

        strategy = _load_strategy(path)
        data = _generate_market(data_track)
        daily, avg_signal, group_series = _run_strategy_backtest(strategy, data)
        metrics = _compute_metrics(daily)
        metrics["stocks"] = _compute_stocks(avg_signal)
        metrics["groups"] = _compute_groups(group_series, metrics["curve"]["dates"])
        metrics["daily_pnl"] = _compute_daily_pnl(daily)
        metrics["score_distribution"] = [s["score"] for s in metrics["stocks"]["all"]]
        score = _score(metrics)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            conn.execute(
                "UPDATE submissions SET status='success', score=?, metrics=?, "
                "error_message=NULL, scored_at=? WHERE id=?",
                (score, json.dumps(metrics), now, submission_id),
            )
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            conn.execute(
                "UPDATE submissions SET status='failed', score=NULL, metrics=NULL, "
                "error_message=?, scored_at=? WHERE id=?",
                (err, now, submission_id),
            )


# 防止同一提交被并发重复回测
_running_ids = set()


def start_backtest(submission_id):
    """启动后台线程执行回测（非阻塞，提交接口立即返回）。"""
    if submission_id in _running_ids:
        return
    _running_ids.add(submission_id)

    def _worker():
        try:
            run_backtest(submission_id)
        finally:
            _running_ids.discard(submission_id)

    threading.Thread(target=_worker, daemon=True).start()


if __name__ == "__main__":
    # 本地自测：python backtest_engine.py <submission_id>
    import sys

    if len(sys.argv) > 1:
        run_backtest(int(sys.argv[1]))
        print("回测完成，请查看数据库中的提交状态。")
    else:
        print("用法：python backtest_engine.py <submission_id>")
