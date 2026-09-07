"""真实 A 股回测方法论（适配新平台 quant-platform）。

从旧 Flask 平台的 ``scripts/analysis/`` 脚本组提炼而来，核心算法完全保真：

    - ``scoring.generate_signals``   EWMA-IC 动态加权打分
    - ``backtest.run_factor_backtest`` walk-forward 滚动回测 + 指标

数据访问抽象成 :class:`DataSource` 接口（current / history / latest），
**数据来源目前留空**——真实数据包尚未找回。接入方式见本包 README 或
:mod:`factor_backtest.datasource` 的模块 docstring。
"""

from factor_backtest.datasource import (
    DATA_SEARCH_PATHS,
    DataSource,
    EmptyDataSource,
    ParquetDataSource,
    find_data_dir,
    load_daily_stocks,
)
from factor_backtest.scoring import generate_signals
from factor_backtest.backtest import (
    longshort_weight_table,
    roll_forward_backtest,
    run_factor_backtest,
)

__all__ = [
    "DATA_SEARCH_PATHS",
    "DataSource",
    "EmptyDataSource",
    "ParquetDataSource",
    "find_data_dir",
    "load_daily_stocks",
    "generate_signals",
    "longshort_weight_table",
    "roll_forward_backtest",
    "run_factor_backtest",
]
