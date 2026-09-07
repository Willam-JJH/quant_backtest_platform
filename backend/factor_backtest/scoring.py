"""EWMA-IC 动态加权打分（真实 A 股回测方法论 · Part 1）。

从旧平台 ``scripts/analysis/scoring.py`` 原样提炼而来，核心算法完全一致：
  1. 计算三个评分分项：ReturnRank（收益率排名）、PEScore、PBScore
  2. 基于历史 IC 的 EWMA 平滑 + Softmax 归一化，动态计算权重 WR、WPE、WPB
  3. 合成最终 score

评分方法：EWMA-IC 动态加权
    Score = WR × ReturnRank + WPE × PEScore + WPB × PBScore

其中：
  - ReturnRank：当日收益率 dretwd 的横截面 zscore（越高越好）
  - PEScore：PE（F100103C）的横截面 zscore 取负（PE 越低越好）
  - PBScore：PB（F100401A）的横截面 zscore 取负（PB 越低越好）
  - WR、WPE、WPB：由各因子历史截面 IC 经过 EWMA 平滑 + Softmax 归一化得到；
    当历史数据不足以计算 IC 时，回退为等权（各 1/3）

本模块只依赖 :class:`factor_backtest.datasource.DataSource` 接口（current /
history / latest），不触碰文件系统。数据来源未接入时，``generate_signals``
会自然回退到「仅用 ReturnRank」或返回空信号。
"""

import numpy as np
import pandas as pd


# ============================================================
# 常量配置
# ============================================================
_LOOKBACK_DAYS = 120          # 回看天数（用于计算历史 IC）
_EWMA_HALFLIFE = 20           # EWMA 半衰期（天数），近期权重更大
_MIN_DAYS = 10                # 最少需要多少有效 IC 日才启用动态权重
_SCORE_TRIMMED_RATIO = 0.30   # 去除最终 score 中排在末尾 30% 的极端值


def zscore(values):
    """横截面标准化：zscore = (value - mean(value)) / std(value)"""
    numeric = pd.Series(values, copy=False).replace([np.inf, -np.inf], np.nan)
    spread = numeric.std(skipna=True)
    if not np.isfinite(spread) or spread == 0:
        return numeric.fillna(0.0) * 0.0
    return ((numeric - numeric.mean(skipna=True)) / spread).fillna(0.0)


def _normalize_code(series):
    """统一股票代码为 6 位字符串（避免 regex，使用整数转字符串补零）。"""
    codes = series.astype(str)
    # 去除 ".0" 后缀（pandas 将整数列读为 float 时的常见后缀）
    codes = codes.str.removesuffix(".0")
    return codes.str.zfill(6).str[-6:]


# ============================================================
# 加速版：向量化计算各因子在历史各期的截面 IC
# ============================================================


def _spearman_ic(f_vals, r_vals):
    """计算一组 (factor, return) 对的 Spearman 秩相关系数（IC）。

    假设 f_vals / r_vals 已对齐且无 NaN。
    """
    n = len(f_vals)
    if n < 10:
        return np.nan

    f_rank = f_vals.rank(method="min")
    r_rank = r_vals.rank(method="min")
    f_centered = f_rank - f_rank.mean()
    r_centered = r_rank - r_rank.mean()

    cov = (f_centered * r_centered).sum() / n
    f_std = f_rank.std(ddof=0)
    r_std = r_rank.std(ddof=0)

    if f_std == 0 or r_std == 0:
        return np.nan
    return cov / (f_std * r_std)


def _compute_all_ics(hist: pd.DataFrame, factor_names: list, trim_pct: float = 0.30) -> dict:
    """一次性计算所有因子的历史截面 IC（合并循环，避免重复 groupby + set_index）。

    对每个交易日，对所有因子同时计算 Spearman IC，一次扫描完成。

    Returns
    -------
    dict
        {factor_name: pd.Series(index=交易日, values=IC值)}
    """
    if hist.empty or not factor_names:
        return {}

    # 预建 code 索引，只做一次 set_index（原代码每轮循环每因子都做）
    available = [f for f in factor_names if f in hist.columns]
    if not available:
        return {}

    indexed = hist.set_index("code")
    # 确保 future_ret 存在
    if "future_ret" not in indexed.columns:
        return {}

    # 按交易日分组
    daily_ic = {f: [] for f in available}
    daily_dates = []

    for trddt, day_group in hist.groupby("trddt", sort=True):
        codes = day_group["code"].values
        # 使用 loc 按 code 切片，避免每因子重复 set_index
        day_slice = indexed.loc[codes]

        ret_vals = day_slice["future_ret"].dropna()
        valid_codes = ret_vals.index

        for fname in available:
            f_all = day_slice[fname]
            # 只保留 f 和 ret 共有的 code
            common = f_all.dropna().index.intersection(valid_codes)
            if len(common) < 10:
                continue

            f_vals = f_all.loc[common]
            r_vals = ret_vals.loc[common]

            # 截尾
            lo = f_vals.quantile(trim_pct / 2)
            hi = f_vals.quantile(1 - trim_pct / 2)
            mask = (f_vals >= lo) & (f_vals <= hi)
            f_trim = f_vals[mask]
            r_trim = r_vals[mask]

            ic_val = _spearman_ic(f_trim, r_trim)
            if np.isfinite(ic_val):
                daily_ic[fname].append((trddt, ic_val))

    result = {}
    for fname, pairs in daily_ic.items():
        if pairs:
            dates, vals = zip(*pairs)
            result[fname] = pd.Series(vals, index=dates).sort_index()
        else:
            result[fname] = pd.Series(dtype="float64")
    return result


def _ewma_smooth(ic_series: pd.Series, halflife: int) -> float:
    """对历史 IC 序列做指数加权平均（近期权重大，远期权重小）。"""
    valid = ic_series.dropna().values
    if len(valid) < 3:
        return 0.0

    n = len(valid)
    decay = np.log(2) / halflife
    weights = np.exp(decay * (np.arange(n) - (n - 1)))
    weights /= weights.sum()

    return float(np.dot(valid, weights))


def _softmax(values: np.ndarray) -> np.ndarray:
    """Softmax 归一化，输出和为 1 且元素非负。"""
    v = np.asarray(values, dtype=np.float64) - np.max(values)
    exp_v = np.exp(v)
    return exp_v / np.sum(exp_v)


def _trim_bottom(scores: pd.Series, ratio: float = _SCORE_TRIMMED_RATIO) -> pd.Series:
    """去除最终 score 中排在末尾 ratio 比例的极端值（设为 0）。

    Parameters
    ----------
    scores : pd.Series
        原始分数序列。
    ratio : float
        要去除的末尾比例，默认 0.30（去除后 30%）。

    Returns
    -------
    pd.Series
        处理后分数序列（末尾 ratio 比例的股票分数被置为 0）。
    """
    if scores.empty or ratio <= 0.0 or ratio >= 1.0:
        return scores

    threshold = scores.quantile(ratio)
    scores = scores.copy()
    scores[scores < threshold] = 0.0
    return scores


# ============================================================
# 缓存：避免同一份历史数据重复计算因子和 IC
# ============================================================

_cache_hist_hash = None       # 上次历史数据的 hash
_cache_ewma_weights = None    # 缓存的 EWMA 权重


def _compute_ewma_weights(hist: pd.DataFrame) -> tuple:
    """计算三个评分因子的 EWMA-IC 动态权重（WR, WPE, WPB），带缓存。

    对 dretwd（ReturnRank）、F100103C（PE）、F100401A（PB）分别计算
    历史截面 IC，经 EWMA 平滑 + Softmax 归一化得到动态权重。

    当某因子列在 hist 中不存在时，其 IC 记为 0。
    当所有 IC 绝对值接近 0 或有效因子不足时，回退为等权（各 1/3）。
    """
    global _cache_hist_hash, _cache_ewma_weights

    # 用数据帧的 shape 和前 100 个值的 hash 作为简易缓存 key
    hist_hash = (len(hist), hist["dretwd"].notna().sum(),
                 hash(hist["trddt"].iloc[0]) if not hist.empty else 0)

    if _cache_hist_hash == hist_hash and _cache_ewma_weights is not None:
        return _cache_ewma_weights

    # 准备因子数据：需要 dretwd 用于 future_ret 计算
    hist = hist.dropna(subset=["dretwd"]).copy()
    hist["code"] = _normalize_code(hist["stkcd"])
    hist = hist.sort_values(["code", "trddt"])
    hist["future_ret"] = hist.groupby("code")["dretwd"].shift(-1)

    # 三个评分因子：dretwd（ReturnRank）、F100103C（PE）、F100401A（PB）
    factor_names = ["dretwd", "F100103C", "F100401A"]
    # 只保留 hist 中实际存在的因子列
    available_factors = [f for f in factor_names if f in hist.columns]

    ic_ready = hist.dropna(subset=["future_ret"] + available_factors)

    if ic_ready.empty or len(available_factors) < 1:
        result = None
    else:
        # 一次性计算所有因子的 IC（合并循环，不再每因子单独扫描）
        all_ics = _compute_all_ics(ic_ready, available_factors)
        ewma_vals = {}
        for fname in available_factors:
            ewma_vals[fname] = _ewma_smooth(
                all_ics.get(fname, pd.Series(dtype="float64")), _EWMA_HALFLIFE
            )

        # 填充缺失因子（列不存在 → IC=0）
        ic_list = [ewma_vals.get(f, 0.0) for f in factor_names]
        ic_arr = np.array(ic_list, dtype=np.float64)

        # 若所有 IC 绝对值接近 0（无有效信号），回退等权
        if np.abs(ic_arr).max() < 1e-8:
            sw = np.ones(3) / 3.0
        else:
            sw = _softmax(ic_arr)
        result = sw, ic_arr

    _cache_hist_hash = hist_hash
    _cache_ewma_weights = result
    return result


def generate_signals(data, date):
    """策略信号生成函数（EWMA-IC 动态加权评分）。

    使用 EWMA-IC 动态加权评分：
      1. ReturnRank: 当日收益率 dretwd 的横截面 zscore
      2. PEScore: PE（F100103C）的横截面 zscore 取负
      3. PBScore: PB（F100401A）的横截面 zscore 取负

    评分公式：
      Score = WR × ReturnRank + WPE × PEScore + WPB × PBScore

    其中 WR、WPE、WPB 由历史截面 IC → EWMA 平滑 → Softmax 归一化得到。
    当历史数据不足以计算 IC 时，回退为等权（WR = WPE = WPB = 1/3）。

    Parameters
    ----------
    data : DataSource
        实现 current / history / latest 接口的数据源对象。
    date : str or datetime-like
        当前交易日。

    Returns
    -------
    pd.Series
        以 stkcd 为索引、score 为值的 Series。
    """
    # ════════════════════════════════════════════════════════
    # 第一步：获取当日收益率，计算 ReturnRank
    # ════════════════════════════════════════════════════════
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    if today.empty:
        return pd.Series(dtype="float64")

    return_rank = zscore(today["dretwd"])

    # ════════════════════════════════════════════════════════
    # 第二步：获取最新 PE、PB 因子数据，计算 PEScore 和 PBScore
    # ════════════════════════════════════════════════════════
    factor = data.latest(
        "factor_benchmark.relative_value.FI_T10",
        by="Stkcd",
        columns=["Stkcd", "F100103C", "F100401A"],
        numeric_columns=["F100103C", "F100401A"],
    )

    if factor.empty:
        # 无因子数据时，仅使用 ReturnRank
        result = pd.Series(return_rank.values, index=today["stkcd"])
        return _trim_bottom(result)

    # 统一代码格式并合并
    codes_today = _normalize_code(today["stkcd"])
    factor_codes = _normalize_code(factor["Stkcd"])

    # 去重：同一股票可能在 factor 表中有多条记录（不同报告期），
    # merge 前保留最后一条，避免一对多扩展导致 score 长度与 today 不一致
    factor_df = factor.assign(code=factor_codes)[["code", "F100103C", "F100401A"]]
    factor_df = factor_df.drop_duplicates(subset="code", keep="last")

    merged = today.assign(code=codes_today).merge(
        factor_df,
        on="code",
        how="left",
    )

    # 用 merged 统一计算所有 zscore，避免 return_rank (来自 today) 与
    # pe_score_raw / pb_score_raw (来自 merged) 长度不一致导致 pandas 对齐扩展
    return_rank = zscore(merged["dretwd"])
    pe_score_raw = zscore(merged["F100103C"])
    pb_score_raw = zscore(merged["F100401A"])

    # ════════════════════════════════════════════════════════
    # 第三步：EWMA-IC 动态权重合成最终 score
    # ════════════════════════════════════════════════════════
    try:
        hist = data.history(
            "stock.daily_returns",
            lookback_days=_LOOKBACK_DAYS,
            columns=["stkcd", "trddt", "dretwd"],
            numeric_columns=["dretwd"],
        )
    except Exception:
        hist = pd.DataFrame()

    # 计算动态权重
    ewma_result = _compute_ewma_weights(hist) if not hist.empty else None
    if ewma_result is not None:
        sw, _ic_arr = ewma_result
        wr, wpe, wpb = float(sw[0]), float(sw[1]), float(sw[2])
    else:
        # 回退为等权
        wr = wpe = wpb = 1.0 / 3.0

    score = (
        wr * return_rank
        + wpe * (-pe_score_raw)
        + wpb * (-pb_score_raw)
    )

    # 使用 merged 中的 stkcd 作为 index，确保与 score 长度一致
    result = pd.Series(score.values, index=merged["stkcd"])
    return _trim_bottom(result)
