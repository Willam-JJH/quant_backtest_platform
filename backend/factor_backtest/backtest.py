"""Walk-Forward 滚动回测 + 指标（真实 A 股回测方法论 · Part 2）。

从旧平台 ``scripts/analysis/ranking.py`` 的 ``roll_forward_backtest`` /
``longshort_weight_table`` 提炼而来，核心算法完全一致：

    - 每隔 ``forward_weeks`` 周（约 ``forward_weeks*5`` 个交易日）滚动一个调仓点；
    - 每个调仓点用 ``generate_signals`` 得到当日截面信号，按信号做多空组合
      （centered / 绝对值之和 归一化为权重，多头为正、空头为负）；
    - 持仓期按「信号权重 × 次日收益」逐日累计，首日扣双边成本
      (``COST_RATE`` = 0.08%)；
    - 相邻持仓期净值按日期去重、排序后拼接成完整净值曲线；
    - 同时计算五分位分组（Q1..Q5）各自等权累计净值。

输出统一对齐新平台模拟引擎的 ``metrics`` 结构（``curve`` / ``groups`` /
``daily_pnl`` / ``stocks`` / ``score_distribution`` + 指标），前端图表组件
无需改动即可复用。
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

from factor_backtest.datasource import ParquetDataSource

# 双边手续费 + 滑点 0.08%
COST_RATE = 0.0008

# 年化用的交易日数（与新平台模拟引擎保持一致）
TRADING_DAYS = 252


# ============================================================
# 权重计算
# ============================================================


def longshort_weight_table(score: pd.Series) -> pd.DataFrame:
    """从 score 计算 longshort 权重。"""
    centered = score - score.mean(skipna=True)
    abs_centered = centered.abs()
    gross = abs_centered.sum(skipna=True)
    weighted = (
        (centered * 0.0) if (gross == 0 or not np.isfinite(gross))
        else (centered / gross)
    )
    side = np.where(weighted > 0, "long", np.where(weighted < 0, "short", "flat"))
    return pd.DataFrame({
        "centered_score": centered, "abs_centered_score": abs_centered,
        "weighted_score": weighted, "side": side,
    })


# ============================================================
# 滚动回测（Walk-Forward Backtest）
# ============================================================


def _calc_period_pnl_and_group(daily_all_flat, all_dates, date_index_map, rdate,
                                forward_weeks, generate_signals_func):
    """计算单个调仓周期的组合PnL和五分位分组收益（含完整时间序列）。

    独立函数，可被串行或并行（ProcessPoolExecutor）调用。
    合并了组合PnL与分组收益的计算，避免重复调用 generate_signals_func。

    group_dict 格式: {Q1: pd.Series(每日收益率), Q2: pd.Series(每日收益率), ...}

    返回值: (rdate, pnl_series_or_None, group_dict_or_None, n_long, n_short)
    """
    try:
        adapter = ParquetDataSource(daily_all_flat, rdate)
        score_series = generate_signals_func(adapter, rdate)

        if score_series.empty:
            return (rdate, None, None, 0, 0)

        scores = score_series.dropna()
        if len(scores) < 10:
            return (rdate, None, None, 0, 0)

        centered = scores - scores.mean()
        abs_sum = centered.abs().sum()
        if abs_sum == 0:
            return (rdate, None, None, 0, 0)
        weights = centered / abs_sum

        n_long = int((weights > 0).sum())
        n_short = int((weights < 0).sum())

        # 确定持仓日期范围（O(1) 查找）
        idx = date_index_map.get(rdate, 0)
        end_idx = min(idx + forward_weeks * 5 + 1, len(all_dates))
        hold_dates_list = all_dates[idx:end_idx]

        # stkcd 已预处理为 zfill(6) 格式，直接用
        weight_series = pd.Series(weights.values.astype(np.float64), index=weights.index)

        # 截取持仓期数据做 pivot（pivot 比 pivot_table 快数倍）
        hold_df = daily_all_flat[daily_all_flat["trddt"].isin(hold_dates_list)]
        if hold_df.empty:
            return (rdate, None, None, n_long, n_short)
        hold_pivot = hold_df.pivot(index="trddt", columns="stkcd", values="dretwd")

        common_stks = [s for s in weight_series.index if s in hold_pivot.columns]
        if not common_stks:
            return (rdate, None, None, n_long, n_short)

        weight_sub = weight_series[common_stks].values
        ret_matrix = hold_pivot[common_stks].values

        # 向量化计算组合收益
        daily_returns = np.nansum(ret_matrix * weight_sub, axis=1)
        daily_returns[0] -= COST_RATE * np.abs(weight_sub).sum()
        pnl_series = pd.Series(daily_returns, index=hold_dates_list)

        # 五分位分组收益（与主循环共享 scores，减少一半 signal 调用）
        group_pnl = None
        if len(scores) >= 20:
            try:
                quintiles = pd.qcut(scores, 5, labels=[f"Q{i}" for i in range(1, 6)], duplicates="drop")
            except ValueError:
                scores_sorted = scores.sort_values()
                n = len(scores_sorted)
                labels = [f"Q{i}" for i in range(1, 6)]
                quintiles = pd.Series(index=scores.index, dtype="object")
                for i in range(5):
                    lo = int(i * n / 5)
                    hi = int((i + 1) * n / 5)
                    idx_slice = scores_sorted.iloc[lo:hi].index
                    quintiles.loc[idx_slice] = labels[i]
            group_ret = {}
            for q_label in [f"Q{i}" for i in range(1, 6)]:
                g_stocks = scores[quintiles == q_label].index.tolist()
                g_common = [s for s in g_stocks if s in hold_pivot.columns]
                if not g_common:
                    continue
                g_ret = hold_pivot[g_common].values
                daily_avg = np.nanmean(g_ret, axis=1)
                group_ret[q_label] = pd.Series(daily_avg, index=hold_dates_list)
            group_pnl = group_ret

        return (rdate, pnl_series, group_pnl, n_long, n_short)

    except Exception as e:
        print(f"    [错误] {rdate.date()}: {e}")
        return (rdate, None, None, 0, 0)


def roll_forward_backtest(daily_all, generate_signals_func, target_date=None,
                          num_rebalance=20, forward_weeks=4, parallel=False):
    """历史滚动回测：每隔 forward_weeks*5 个交易日回滚一个调仓点。

    返回 dict：
        rebal_dates    — 调仓日期列表
        full_nav       — pd.Series，多空组合日频净值（从 1 开始）
        daily_ret      — pd.Series，多空组合日收益率
        group_pnl      — {Q1..Q5: pd.Series 各分组日频净值}
        weekly_buy_sell— DataFrame（调仓买入/卖出名义量）
    """
    if daily_all is None or daily_all.empty or "trddt" not in daily_all.columns:
        return None
    all_dates = sorted(daily_all["trddt"].unique())
    if not all_dates:
        return None
    if target_date is None:
        target_date = all_dates[-1]
    target_date = pd.Timestamp(target_date)
    if target_date not in all_dates:
        # 容错：取不超过 target_date 的最近交易日
        prior = [d for d in all_dates if d <= target_date]
        target_date = prior[-1] if prior else all_dates[0]

    end_idx = all_dates.index(target_date)
    step = forward_weeks * 5
    rebal_indices = list(range(end_idx, -1, -step))[::-1]
    if len(rebal_indices) > num_rebalance:
        rebal_indices = rebal_indices[-num_rebalance:]
    rebal_dates = [all_dates[i] for i in rebal_indices]

    # 注意：parallel=True 在 Windows spawn 语义下会把完整 daily_all 逐 task
    # pickle 到每个 worker（内存成倍膨胀），且 generate_signals_func 必须可 pickle。
    # 默认关闭；真实全量 A 股数据下更推荐串行或改用共享内存方案。
    parallel = parallel and len(rebal_dates) >= 3

    print(f"\n[滚动回测] {len(rebal_dates)} 个调仓点, "
          f"{rebal_dates[0].date()} ~ {rebal_dates[-1].date()}, "
          f"每 {forward_weeks} 周调仓, "
          f"{'并行' if parallel else '串行'}模式")

    # 预处理 stkcd 格式 + 构建日期索引映射（O(1) 查找）
    daily_all_flat = daily_all.copy()
    daily_all_flat["stkcd"] = daily_all_flat["stkcd"].astype(str).str.zfill(6)
    date_index_map = {d: i for i, d in enumerate(all_dates)}

    # 准备参数
    task_args = [
        (daily_all_flat, all_dates, date_index_map, rdate, forward_weeks, generate_signals_func)
        for rdate in rebal_dates
    ]

    all_portfolio_pnls = {}
    all_group_pnls = {}

    if parallel:
        max_workers = min(len(rebal_dates), os.cpu_count() or 4)
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_calc_period_pnl_and_group, *args): args[3]
                       for args in task_args}
            completed = 0
            total = len(futures)
            for future in as_completed(futures):
                rdate = futures[future]
                completed += 1
                try:
                    res_rdate, pnl, group_pnl, n_long, n_short = future.result()
                    if pnl is not None:
                        all_portfolio_pnls[res_rdate] = pnl
                    if group_pnl is not None:
                        all_group_pnls[res_rdate] = group_pnl
                    status = f"ok (多头={n_long}, 空头={n_short})" if pnl is not None else "跳过"
                    print(f"  回测 [{completed}/{total}] {res_rdate.date()} {status}")
                except Exception as e:
                    print(f"  回测 [{completed}/{total}] {rdate.date()} 异常: {e}")
    else:
        # 串行模式（仍合并了分组收益计算，省去一半 generate_signals 调用）
        for i, rdate in enumerate(rebal_dates):
            res_rdate, pnl, group_pnl, n_long, n_short = _calc_period_pnl_and_group(
                daily_all_flat, all_dates, date_index_map, rdate, forward_weeks, generate_signals_func
            )
            if pnl is not None:
                all_portfolio_pnls[res_rdate] = pnl
            if group_pnl is not None:
                all_group_pnls[res_rdate] = group_pnl
            status = f"ok (多头={n_long}, 空头={n_short})" if pnl is not None else "跳过"
            print(f"  回测 [{i+1}/{len(rebal_dates)}] {res_rdate.date()} {status}")

    if not all_portfolio_pnls:
        print("[错误] 滚动回测无有效结果")
        return None

    # --- 向量化 NAV 构建 ---
    nav_parts = [all_portfolio_pnls[r] for r in rebal_dates if r in all_portfolio_pnls]
    if not nav_parts:
        return None

    combined_returns = pd.concat(nav_parts)
    # 去重（相邻持仓期可能在交界处有重复日期，取首次出现的值）
    combined_returns = combined_returns[~combined_returns.index.duplicated(keep="first")]
    combined_returns = combined_returns.sort_index()

    full_nav = np.cumprod(1 + combined_returns.values)
    full_nav = pd.Series(full_nav, index=combined_returns.index)

    # 逐日收益直接取合并后的真实收益序列。切勿像旧实现那样对净值强制改首值
    # 再 pct_change——那会抹掉首日收益，并把第二日错算成两日累计收益。
    daily_ret = combined_returns

    # --- 合并分组收益（构建完整的时间序列 NAV） ---
    group_pnls = {}
    if all_group_pnls:
        for q in [f"Q{i}" for i in range(1, 6)]:
            # 收集该组在所有调仓周期的收益率序列
            q_series_list = [g[q] for g in all_group_pnls.values() if q in g and g[q] is not None]
            if not q_series_list:
                group_pnls[q] = pd.Series(dtype="float64")
                continue
            # 合并所有周期的收益率，去重后排序
            combined = pd.concat(q_series_list)
            combined = combined[~combined.index.duplicated(keep="first")]
            combined = combined.sort_index()
            # 计算累计净值
            group_nav = np.cumprod(1 + combined.values)
            group_pnls[q] = pd.Series(group_nav, index=combined.index)

    weekly_buy_sell = pd.DataFrame([
        {"week_end": rdate, "buy_volume": 0.5, "sell_volume": 0.5}
        for rdate in rebal_dates
    ])

    return {
        "rebal_dates": rebal_dates,
        "full_nav": full_nav,
        "daily_ret": daily_ret,
        "group_pnl": group_pnls,
        "weekly_buy_sell": weekly_buy_sell,
    }


# ============================================================
# 指标与输出结构（对齐新平台模拟引擎 metrics）
# ============================================================


def _compute_metrics_from_returns(rets):
    """由日收益序列计算全部评分指标（算法与新平台 backtest_engine 一致）。"""
    n = len(rets)
    if n == 0:
        raise ValueError("回测窗口为空，无法计算指标")

    # 累计收益曲线（复利），values[i] = 第 i 天结束时的累计收益
    eq = 1.0
    cum_values = []
    for r in rets:
        eq *= (1.0 + r)
        cum_values.append(eq - 1.0)
    cumulative_return = eq - 1.0

    annual_return = (1.0 + cumulative_return) ** (TRADING_DAYS / n) - 1.0

    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / n
    std = math.sqrt(var)
    daily_std = std
    volatility = std * math.sqrt(TRADING_DAYS)
    sharpe = (mean / std * math.sqrt(TRADING_DAYS)) if std > 0 else 0.0

    peak = 0.0
    max_dd = 0.0
    for v in cum_values:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)

    win_rate = sum(1 for r in rets if r > 0) / n

    return {
        "annual_return": annual_return,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "volatility": volatility,
        "win_rate": win_rate,
        "cumulative_return": cumulative_return,
        "daily_std": daily_std,
    }


def _compute_stocks_from_series(score_series, top_n=10):
    """由截面信号生成多空候选名单（对齐新平台 _compute_stocks 输出格式）。"""
    s = score_series.dropna()
    ranked = s.sort_values(ascending=False)

    def fmt(pairs):
        return [{"code": str(c), "score": round(float(v), 6)} for c, v in pairs]

    items = [(c, v) for c, v in ranked.items()]
    return {
        "top": fmt(items[:top_n]),
        "bottom": fmt(items[-top_n:][::-1]),
        "all": fmt(items),
    }


def run_factor_backtest(daily_all, generate_signals_func, target_date=None,
                        num_rebalance=20, forward_weeks=4, top_n=10):
    """真实 A 股 walk-forward 回测主入口，输出新平台 metrics 结构。

    Parameters
    ----------
    daily_all : pd.DataFrame
        已加载的日行情（含 trddt / stkcd / dretwd 列），由
        ``datasource.load_daily_stocks`` 返回。
    generate_signals_func : callable
        信号函数 ``(data_source, date) -> pd.Series``，如
        ``factor_backtest.scoring.generate_signals``。

    Returns
    -------
    dict or None
        与新平台模拟引擎一致的 metrics 结构；无有效结果时返回 None。
    """
    if daily_all is None or daily_all.empty or "trddt" not in daily_all.columns:
        return None
    all_dates = sorted(daily_all["trddt"].unique())
    if not all_dates:
        return None
    if target_date is None:
        target_date = all_dates[-1]
    target_date = pd.Timestamp(target_date)

    # 1. walk-forward 回测
    bt = roll_forward_backtest(
        daily_all, generate_signals_func,
        target_date=target_date,
        num_rebalance=num_rebalance,
        forward_weeks=forward_weeks,
        parallel=False,
    )
    if bt is None:
        return None

    full_nav = bt["full_nav"]
    daily_ret = bt["daily_ret"]
    group_pnl = bt["group_pnl"]

    # 2. 指标 + 曲线
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in full_nav.index]
    rets = [float(r) for r in daily_ret.values]
    metrics = _compute_metrics_from_returns(rets)
    metrics["curve"] = {
        "dates": dates,
        "values": [float(v - 1.0) for v in full_nav.values],
    }
    metrics["daily_pnl"] = {"dates": dates, "values": rets}

    # 3. 分组累计曲线（对齐主曲线日期）
    group_series = {}
    for q in [f"Q{i}" for i in range(1, 6)]:
        nav = group_pnl.get(q)
        if nav is None or len(nav) < 2:
            group_series[q] = [0.0] * len(dates)
        else:
            aligned = nav.reindex(full_nav.index).ffill().fillna(0.0)
            group_series[q] = [float(v - 1.0) for v in aligned.values]
    metrics["groups"] = {"dates": dates, "series": group_series}

    # 4. 个股打分（target_date 截面）
    adapter = ParquetDataSource(daily_all, target_date)
    score_series = generate_signals_func(adapter, target_date)
    stocks = _compute_stocks_from_series(score_series, top_n)
    metrics["stocks"] = stocks
    metrics["score_distribution"] = [s["score"] for s in stocks["all"]]

    return metrics
