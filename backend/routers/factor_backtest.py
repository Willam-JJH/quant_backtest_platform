"""真实 A 股因子回测路由。

提供真实数据回测的入口（EWMA-IC 打分 + walk-forward 回测）。数据来源目前
**留空**：真实数据包未接入时，接口返回明确状态，前端可据此展示「数据未接入」。
"""

from fastapi import APIRouter, HTTPException

from factor_backtest import (
    find_data_dir,
    generate_signals,
    load_daily_stocks,
    run_factor_backtest,
)
from i18n import _

router = APIRouter(prefix="/api/factor-backtest", tags=["factor-backtest"])


@router.get("/status")
def factor_backtest_status():
    """返回真实数据回测的数据源状态。"""
    data_dir = find_data_dir(silent=True)
    return {
        "available": data_dir is not None,
        "data_dir": str(data_dir) if data_dir else None,
        "hint": _("真实数据包未接入：请在 datasource.DATA_SEARCH_PATHS 之一放置数据，或显式传入 data_dir。"),
    }


@router.post("/run")
def factor_backtest_run(
    target_date: str = None,
    num_rebalance: int = 20,
    forward_weeks: int = 4,
    top_n: int = 10,
):
    """用真实数据跑一次 EWMA-IC 因子 walk-forward 回测。

    数据源空时返回 503 + 明确提示；数据到位后返回完整 metrics
    （结构与新平台模拟引擎一致，前端图表组件可直接复用）。
    """
    try:
        daily_all, target_date = load_daily_stocks(
            data_dir=None, target_date=target_date
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=_("数据或日期参数无效：{exc}", exc=exc))

    metrics = run_factor_backtest(
        daily_all,
        generate_signals,
        target_date=target_date,
        num_rebalance=num_rebalance,
        forward_weeks=forward_weeks,
        top_n=top_n,
    )
    if metrics is None:
        raise HTTPException(status_code=400, detail=_("回测未能生成有效结果（数据可能不足）"))
    return metrics
