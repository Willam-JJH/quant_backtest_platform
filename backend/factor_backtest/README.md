# 真实 A 股回测方法论（factor_backtest）

从旧 Flask「量化评分系统」的 `scripts/analysis/` 脚本组移植而来的真实回测方法论，
适配到新平台 quant-platform 的 backend 包。

## 组成

| 文件 | 来源 | 内容 |
|------|------|------|
| `datasource.py` | `ranking.py` 的 `PlatformDataAdapter` + `load_daily_stocks` | 数据源抽象（`DataSource` / `EmptyDataSource` / `ParquetDataSource`）+ 数据加载 |
| `scoring.py` | `scoring.py` | EWMA-IC 动态加权打分（`generate_signals`） |
| `backtest.py` | `ranking.py` 的 `roll_forward_backtest` + `longshort_weight_table` | walk-forward 滚动回测 + 指标 |

## 数据接入（当前留空）

真实数据包尚未找回，因此 `DataSource` 目前只有空实现。待数据到位后：

1. 把数据目录放到 `datasource.DATA_SEARCH_PATHS` 之一（`quantitative_finance/` 下的
   `distribute/learning/distribute`、`new_data/distribute` 或 `data`），
   目录内需含 `stock/daily_returns.parquet`、`basic/company_info.csv` 等；
2. 若需要 PE/PB 因子（`scoring` 的 PEScore / PBScore 分项），在
   `ParquetDataSource.latest` 中补上 `factor_benchmark.relative_value.FI_T10`
   的读取逻辑；不补也能跑，只是打分回退到「仅用 ReturnRank」。

## 用法

```python
from factor_backtest import load_daily_stocks, generate_signals, run_factor_backtest

# 1. 加载日行情（数据到位后自动发现，或显式传 data_dir=...）
daily_all, target_date = load_daily_stocks()          # 数据未接入时会抛 FileNotFoundError

# 2. 跑 walk-forward 回测，输出与新平台模拟引擎一致的 metrics 结构
metrics = run_factor_backtest(daily_all, generate_signals, target_date=target_date)

# metrics 含：curve / groups / daily_pnl / stocks / score_distribution
#          + annual_return / sharpe / max_drawdown / volatility / win_rate / ...
```

## API

后端提供 `routers/factor_backtest.py`：

- `GET  /api/factor-backtest/status`  — 数据源是否就绪
- `POST /api/factor-backtest/run`     — 跑一次真实因子回测（数据空时返回 503 + 提示）
