"""真实 A 股数据源抽象层（数据来源暂留空）。

从旧平台 ``scripts/analysis/ranking.py`` 的 ``PlatformDataAdapter`` 提炼而来，
把「数据访问」抽象成统一接口，让 EWMA-IC 打分（``scoring.py``）与回测引擎
（``backtest.py``）不再直接触碰文件系统，只依赖 :class:`DataSource` 的三个方法：

    - current(dataset, ...)   当日截面
    - history(dataset, ...)   历史窗口
    - latest(dataset, ...)    最新因子（PE/PB 等）

当前状态：**数据来源留空**。真实数据包（``daily_returns.parquet`` /
``company_info.csv`` / PE·PB 因子表）尚未找回。待数据到位后，只需：

    1. 把数据目录放到 :data:`DATA_SEARCH_PATHS` 之一（或直接传 ``data_dir``
       给 :func:`load_daily_stocks`）；
    2. 在 :meth:`ParquetDataSource.latest` 中补上 PE/PB 因子表的读取。

即可让整套真实回测跑起来，其余代码无需改动。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

# quantitative_finance/ 根目录
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 数据搜索路径（与旧平台一致，数据包找回后放到任一目录即可被自动发现）
DATA_SEARCH_PATHS = [
    PROJECT_ROOT / "distribute" / "learning" / "distribute",
    PROJECT_ROOT / "new_data" / "distribute",
    PROJECT_ROOT / "data",
]


def find_data_dir(silent: bool = False):
    """返回第一个存在的数据目录；找不到返回 None。"""
    for p in DATA_SEARCH_PATHS:
        resolved = p.resolve()
        if resolved.exists():
            if not silent:
                print(f"[信息] 使用数据目录: {resolved}")
            return resolved
    if not silent:
        print("[错误] 找不到数据目录！")
        for p in DATA_SEARCH_PATHS:
            print(f"  尝试过: {p.resolve()}")
    return None


class DataSource(ABC):
    """真实数据源统一接口。打分策略只依赖这三个方法，不关心数据来源。"""

    @abstractmethod
    def current(self, dataset, columns=None, numeric_columns=None):
        """返回目标日期的当日截面 DataFrame。"""

    @abstractmethod
    def history(self, dataset, lookback_days=120, columns=None, numeric_columns=None):
        """返回截至目标日期的历史窗口 DataFrame。"""

    @abstractmethod
    def latest(self, dataset, by=None, columns=None, numeric_columns=None):
        """返回最新因子 DataFrame（如 PE/PB）。"""


class EmptyDataSource(DataSource):
    """空数据源：真实数据包未接入时的占位实现，全部返回空 DataFrame。

    打分策略在空数据下会自然返回空信号；回测引擎对空数据返回 None
    （不会崩溃）。用于单元测试与占位。API 层的数据就绪判断由
    find_data_dir / load_daily_stocks 完成。
    """

    def __init__(self, reason: str = "真实数据包未接入"):
        self.reason = reason

    def current(self, *args, **kwargs):
        return pd.DataFrame()

    def history(self, *args, **kwargs):
        return pd.DataFrame()

    def latest(self, *args, **kwargs):
        return pd.DataFrame()


class ParquetDataSource(DataSource):
    """基于本地 Parquet 日行情的真实数据源（数据包找回后可用）。

    等价于旧平台 ``PlatformDataAdapter``：把一个已加载的日行情 DataFrame
    （含 trddt / stkcd / dretwd 等列）封装成 current/history 接口。
    latest() 暂返回空 DataFrame——PE/PB 因子表尚未接入，打分策略会自动
    回退到「仅用 ReturnRank」的路径。
    """

    def __init__(self, daily_df: pd.DataFrame, target_date):
        self._daily = daily_df
        self._target_date = pd.Timestamp(target_date)
        # 预计算排序后的日期列表（只做一次）
        self._all_dates_cache = sorted(self._daily["trddt"].unique())

    def current(self, dataset, columns=None, numeric_columns=None):
        if dataset != "stock.daily_returns":
            raise KeyError(f"不支持的 dataset: {dataset}")
        cur = self._daily[self._daily["trddt"] == self._target_date]
        if cur.empty:
            return pd.DataFrame()
        cols = columns if columns else cur.columns.tolist()
        cols = [c for c in cols if c in cur.columns]
        return cur[cols]

    def history(self, dataset, lookback_days=120, columns=None, numeric_columns=None):
        if dataset != "stock.daily_returns":
            raise KeyError(f"不支持的 dataset: {dataset}")
        all_dates = self._all_dates_cache
        try:
            target_idx = all_dates.index(self._target_date)
        except ValueError:
            return pd.DataFrame()
        start_idx = max(0, target_idx - lookback_days)
        lookback_dates = all_dates[start_idx:target_idx]
        if not lookback_dates:
            return pd.DataFrame()
        mask = self._daily["trddt"].isin(lookback_dates)
        hist = self._daily.loc[mask].copy()  # 返回时才 copy，避免修改原数据
        if hist.empty:
            return pd.DataFrame()
        cols = columns if columns else hist.columns.tolist()
        cols = [c for c in cols if c in hist.columns]
        return hist[cols]

    def latest(self, dataset, by=None, columns=None, numeric_columns=None):
        # PE/PB 因子表尚未接入：返回空，让打分策略回退到仅 ReturnRank
        return pd.DataFrame()


def load_daily_stocks(data_dir=None, target_date=None, use_market_types=None):
    """加载指定交易日的股票截面及其历史数据（数据包找回后可用）。

    数据目录为空（未配置）时抛出 FileNotFoundError，提示先接入真实数据包。
    """
    if data_dir is None:
        data_dir = find_data_dir(silent=True)
    if data_dir is None:
        raise FileNotFoundError(
            "真实数据包未接入：找不到数据目录。请把数据包放到 "
            + " / ".join(str(p) for p in DATA_SEARCH_PATHS)
            + " 之一，或显式传入 data_dir。"
        )

    data_dir = Path(data_dir)
    stock_dir = data_dir / "stock"
    basic_dir = data_dir / "basic"

    print("[读取] 日行情表 ...")
    dp = stock_dir / "daily_returns.parquet"
    if not dp.exists():
        raise FileNotFoundError(f"找不到: {dp}")
    daily = pd.read_parquet(dp)
    print(
        f"  总行数: {len(daily):,}, "
        f"日期: {daily['trddt'].min().date()} ~ {daily['trddt'].max().date()}"
    )

    if target_date is None:
        target_date = daily["trddt"].max()
        print(f"  自动选择最新交易日: {target_date.date()}")
    else:
        target_date = pd.Timestamp(target_date)

    fmt = "all" if use_market_types == "all" else (use_market_types or [1, 4])
    if fmt != "all":
        before = len(daily)
        daily = daily[daily["markettype"].isin(fmt)].copy()
        print(f"  市场类型 {fmt} 筛选: {len(daily):,}/{before:,}")

    daily["stkcd"] = daily["stkcd"].astype(str).str.zfill(6)

    if target_date not in daily["trddt"].unique():
        raise ValueError(f"{target_date.date()} 无数据")

    ip = basic_dir / "company_info.csv"
    if ip.exists():
        print("[读取] company_info.csv ...")
        info = pd.read_csv(ip)
        info["stkcd"] = info["stkcd"].astype(str).str.zfill(6)
        merge_cols = [c for c in ["stkcd", "stknme", "indnme", "province", "city"]
                      if c in info.columns]
        daily = daily.merge(info[merge_cols], on="stkcd", how="left")
        matched = daily["stknme"].notna().sum() if "stknme" in daily.columns else 0
        print(f"  合并完成, {matched:,} 只匹配到基本信息")
    else:
        daily["stknme"] = None
        daily["indnme"] = None

    ind_path = basic_dir / "STK_INDUSTRYCLASS.csv"
    if ind_path.exists():
        print("[读取] STK_INDUSTRYCLASS.csv ...")
        ind = pd.read_csv(ind_path)
        if "Symbol" in ind.columns:
            ind["stkcd"] = ind["Symbol"].astype(str).str.zfill(6)
            if "ImplementDate" in ind.columns:
                ind = ind.sort_values("ImplementDate", ascending=False)
            daily = daily.merge(
                ind[["stkcd", "IndustryCode", "IndustryName"]].drop_duplicates("stkcd"),
                on="stkcd", how="left",
            )

    return daily.reset_index(drop=True), target_date
