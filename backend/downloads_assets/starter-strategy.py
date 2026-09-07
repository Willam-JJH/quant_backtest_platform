# -*- coding: utf-8 -*-
"""
SickFun 策略模板 —— 动量示例
=============================
提交前请确保本文件包含 generate_signals(data, date) 函数。

函数约定：
    data : 一个 dict 或对象，至少包含 data.hist（含历史行情）等字段；
           具体结构见「快速开始指南」。
    date : str，格式 'YYYY-MM-DD'，代表当天。
    返回 ：pd.Series，index 为股票代码，值为信号强度。
           信号值越大 → 越看多；系统按信号分 5 组回测。

把本模板当作起点：替换 / 补充你的因子逻辑即可。
"""

import pandas as pd


def generate_signals(data, date):
    """示例动量策略：过去 20 日收益越高，信号越强。"""
    try:
        # data.hist 是含历史行情的 DataFrame，列含代码(code)、日期(date)、收盘价(close)
        hist = data.hist
        hist["date"] = pd.to_datetime(hist["date"])
        upto = hist[hist["date"] <= pd.to_datetime(date)].copy()

        # 取每只股票最近 20 个交易日的收盘价，计算动量
        recent = (
            upto.sort_values("date")
            .groupby("code")
            .tail(20)
            .reset_index(drop=True)
        )
        pivot = recent.pivot_table(index="code", columns="date", values="close", aggfunc="last")
        # 防御：若窗口不足则用可得数据
        momentum = pivot.iloc[:, -1] / pivot.iloc[:, 0] - 1
        return momentum.fillna(0.0)
    except Exception:
        # 兜底：任何报错都返回全 0 信号，保证可运行
        codes = getattr(getattr(data, "hist", None), "code", None)
        if codes is None:
            return pd.Series(dtype=float)
        return pd.Series(0.0, index=pd.unique(codes))


if __name__ == "__main__":
    # 本地自检：构造一份迷你数据跑通函数
    import numpy as np

    demo = {
        "hist": pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=40).repeat(3),
                "code": list("ABC") * 40,
                "close": np.random.default_rng(0).random(120) * 20 + 10,
            }
        )
    }
    print(generate_signals(demo, "2025-02-15"))
