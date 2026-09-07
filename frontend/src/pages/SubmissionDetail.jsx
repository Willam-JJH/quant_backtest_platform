// 提交详情页面：KPI 卡片 + 指标明细 + 累计收益曲线 + 源代码弹窗
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  LineChart,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

import StatusBadge from "../components/StatusBadge.jsx";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";

// 指标名称与说明
const METRIC_INFO = {
  annual_return: { label: "年化收益率", fmt: "pct", desc: "策略年度化收益率" },
  sharpe: { label: "夏普比率", fmt: "num", desc: "单位风险的超额收益" },
  max_drawdown: { label: "最大回撤", fmt: "pct", desc: "区间内最大亏损幅度" },
  volatility: { label: "波动率", fmt: "pct", desc: "年化收益波动" },
  win_rate: { label: "胜率", fmt: "pct", desc: "盈利天数占比" },
  cumulative_return: { label: "累计收益", fmt: "pct", desc: "回测期累计收益率" },
  daily_std: { label: "日收益标准差", fmt: "pct", desc: "单日收益离散程度" },
};

// 分组曲线颜色（G1~G5）
const GROUP_COLORS = ["#3b82f6", "#34d399", "#fbbf24", "#f87171", "#a78bfa"];

function fmtVal(key, v) {
  const info = METRIC_INFO[key];
  const num = typeof v === "number" ? v : Number(v);
  if (Number.isNaN(num)) return String(v ?? "-");
  if (info?.fmt === "pct") return `${(num * 100).toFixed(2)}%`;
  return num.toFixed(2);
}

export default function SubmissionDetail() {
  const { submissionId } = useParams();
  const { team } = useAuth();
  const { t } = useI18n();

  // 提交数据
  const [sub, setSub] = useState(null);
  const [state, setState] = useState("loading"); // loading | ok | error | notfound
  // 原始错误弹层
  const [rawError, setRawError] = useState("");
  const [showRaw, setShowRaw] = useState(false);
  // 源代码弹窗
  const [showSource, setShowSource] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/submissions/${submissionId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => {
        if (cancelled) return;
        setSub(d);
        setState(d.status === "failed" ? "failed" : "ok");
      })
      .catch((code) => {
        if (cancelled) return;
        setState(code === 404 ? "notfound" : "error");
      });
    return () => {
      cancelled = true;
    };
  }, [submissionId]);

  async function loadRawError() {
    try {
      const res = await fetch(`/api/submissions/${submissionId}/raw-error`);
      setRawError(res.ok ? await res.text() : t("无法获取原始错误"));
      setShowRaw(true);
    } catch {
      setRawError(t("网络错误"));
      setShowRaw(true);
    }
  }

  if (state === "loading") return <div className="home-loading">{t("加载中...")}</div>;
  if (state === "notfound")
    return (
      <div className="card error-card">
        <h2>{t("提交不存在")}</h2>
        <Link to="/history" className="btn btn-primary">{t("返回历史记录")}</Link>
      </div>
    );
  if (state === "error")
    return (
      <div className="card error-card">
        <h2>{t("数据加载失败")}</h2>
        <Link to="/history" className="btn btn-primary">{t("返回历史记录")}</Link>
      </div>
    );

  const m = (sub.metrics && typeof sub.metrics === "object" ? sub.metrics : {}) || {};

  // 头部指标卡片：score + 常见指标
  const kpis = [{ key: "score", label: t("综合得分"), value: sub.score }];
  for (const key of ["annual_return", "sharpe", "max_drawdown", "volatility"]) {
    if (m[key] !== undefined && m[key] !== null) {
      kpis.push({ key, label: t(METRIC_INFO[key].label), value: fmtVal(key, m[key]) });
    }
  }

  // 收益曲线数据（metrics.curve: { dates:[], values:[] }，values 为小数累计收益）
  const curve = m.curve;
  const chartData =
    curve?.dates && curve?.values
      ? curve.dates.map((d, i) => ({
          date: String(d).slice(0, 10),
          ret: Number(curve.values[i]),
        }))
      : [];

  // 分组累计收益曲线（metrics.groups: { dates:[], series:{G1..G5:[...]}}）
  const groups = m.groups;
  const groupNames = groups?.series ? Object.keys(groups.series) : [];
  const groupData =
    groups?.dates && groups?.series
      ? groups.dates.map((d, i) => {
          const row = { date: String(d).slice(0, 10) };
          groupNames.forEach((g) => {
            row[g] = Number(groups.series[g][i]);
          });
          return row;
        })
      : [];

  // 每日盈亏（metrics.daily_pnl: { dates:[], values:[] }）
  const pnl = m.daily_pnl;
  const pnlData =
    pnl?.dates && pnl?.values
      ? pnl.dates.map((d, i) => ({
          date: String(d).slice(0, 10),
          pnl: Number(pnl.values[i]),
        }))
      : [];

  // score 分布直方图（metrics.score_distribution: 个股平均信号列表）
  const SCORE_BINS = 20;
  const rawScores = Array.isArray(m.score_distribution)
    ? m.score_distribution.map(Number).filter((x) => Number.isFinite(x))
    : [];
  let scoreBins = [];
  if (rawScores.length) {
    const min = Math.min(...rawScores);
    const max = Math.max(...rawScores);
    const span = max - min || 1;
    const counts = new Array(SCORE_BINS).fill(0);
    rawScores.forEach((s) => {
      let idx = Math.floor(((s - min) / span) * SCORE_BINS);
      if (idx >= SCORE_BINS) idx = SCORE_BINS - 1;
      if (idx < 0) idx = 0;
      counts[idx] += 1;
    });
    scoreBins = counts.map((count, i) => {
      const lo = min + (span * i) / SCORE_BINS;
      return { range: `${lo.toFixed(3)}`, count };
    });
  }

  // 指标明细表
  const metricKeys = Object.keys(METRIC_INFO).filter((k) => m[k] !== undefined);

  return (
    <div className="detail">
      {/* 基本信息 */}
      <section className="detail-head">
        <h1 className="page-title">{t("📊 提交详情 #{id}", { id: sub.id })}</h1>
        <div className="detail-meta card">
          <span><b>{t("队伍：")}</b>{sub.team_display_name}</span>
          <span className="track-chip">{sub.data_track}</span>
          <StatusBadge status={sub.status} />
          <span className="muted">{t("提交于 {time}", { time: sub.submitted_at?.slice(0, 16) })}</span>
          {sub.scored_at && <span className="muted">{t("评分于 {time}", { time: sub.scored_at?.slice(0, 16) })}</span>}
        </div>
      </section>

      {/* failed：错误卡片 */}
      {sub.status === "failed" && (
        <section className="card error-card detail-error">
          <h2>{t("❌ 本次评分失败")}</h2>
          <p>{sub.error_message || t("无错误信息")}</p>
          <button className="btn btn-danger" onClick={loadRawError}>
            {t("查看原始错误")}
          </button>
        </section>
      )}

      {/* success：核心展示 */}
      {sub.status === "success" && (
        <>
          {/* 评分概览 KPI */}
          <section className="kpi-row">
            {kpis.map((k) => (
              <div className="kpi-card" key={k.key}>
                <div className={`kpi-value ${k.key === "max_drawdown" ? "neg" : ""}`}>
                  {k.value}
                </div>
                <div className="kpi-label">{k.label}</div>
              </div>
            ))}
          </section>

          {/* 多空候选股（按全周期平均信号） */}
          {m.stocks && (m.stocks.top?.length || m.stocks.bottom?.length) && (
            <section className="card">
              <h2>{t("📌 多空候选股")}</h2>
              <p className="muted">{t("全周期平均信号最高者为多头候选，最低者为空头候选")}</p>
              <div className="stocks-grid">
                <div>
                  <h3 className="stocks-title long">{t("🟢 多头 Top {n}", { n: m.stocks.top?.length || 0 })}</h3>
                  <table className="table">
                    <thead><tr><th>#</th><th>{t("代码")}</th><th>{t("平均信号")}</th></tr></thead>
                    <tbody>
                      {(m.stocks.top || []).map((s, i) => (
                        <tr key={s.code}>
                          <td className="muted">{i + 1}</td>
                          <td><b>{s.code}</b></td>
                          <td className="score-high">{(s.score > 0 ? "+" : "") + s.score.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <h3 className="stocks-title short">{t("🔴 空头 Bottom {n}", { n: m.stocks.bottom?.length || 0 })}</h3>
                  <table className="table">
                    <thead><tr><th>#</th><th>{t("代码")}</th><th>{t("平均信号")}</th></tr></thead>
                    <tbody>
                      {(m.stocks.bottom || []).map((s, i) => (
                        <tr key={s.code}>
                          <td className="muted">{i + 1}</td>
                          <td><b>{s.code}</b></td>
                          <td className="score-high">{(s.score > 0 ? "+" : "") + s.score.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          )}

          <div className="detail-grid">
            {/* 指标明细表 */}
            <section className="card">
              <h2>{t("指标明细")}</h2>
              {metricKeys.length ? (
                <table className="table">
                  <thead>
                    <tr><th>{t("指标")}</th><th>{t("数值")}</th><th>{t("说明")}</th></tr>
                  </thead>
                  <tbody>
                    {metricKeys.map((k) => (
                      <tr key={k}>
                        <td><b>{t(METRIC_INFO[k].label)}</b></td>
                        <td className="score-high">{fmtVal(k, m[k])}</td>
                        <td className="muted">{t(METRIC_INFO[k].desc)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">{t("暂无明细指标")}</p>
              )}
            </section>

            {/* 累计收益曲线 */}
            <section className="card">
              <h2>{t("累计收益率")}</h2>
              {chartData.length > 1 ? (
                <div className="chart-box">
                  <ResponsiveContainer width="100%" height={280}>
                    <ComposedChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                      <defs>
                        <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.28} />
                          <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="date"
                        stroke="#64748b"
                        tick={{ fill: "#94a3b8", fontSize: 11 }}
                        tickLine={false}
                        axisLine={{ stroke: "#334155" }}
                        minTickGap={28}
                      />
                      <YAxis
                        tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                        stroke="#64748b"
                        tick={{ fill: "#94a3b8", fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                        width={52}
                      />
                      <Tooltip
                        formatter={(v) => [`${(v * 100).toFixed(2)}%`, t("累计收益")]}
                        labelFormatter={(l) => t("日期：{d}", { d: l })}
                        contentStyle={{
                          background: "#0f172a",
                          border: "1px solid #334155",
                          borderRadius: 8,
                          color: "#e2e8f0",
                        }}
                        itemStyle={{ color: "#3b82f6" }}
                      />
                      <Area type="monotone" dataKey="ret" stroke="none" fill="url(#eqFill)" />
                      <Line
                        type="monotone"
                        dataKey="ret"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={false}
                        activeDot={{ r: 4, fill: "#3b82f6", stroke: "#0f172a", strokeWidth: 2 }}
                        isAnimationActive
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="chart-empty">
                  <p className="empty-icon">📈</p>
                  <p className="muted">{t("收益曲线数据生成中…")}</p>
                </div>
              )}
            </section>
          </div>

          {/* 分组累计收益曲线（G1~G5） */}
          {groupData.length > 1 && (
            <section className="card">
              <h2>{t("分组累计收益")}</h2>
              <p className="muted">{t("信号由低到高分为 5 组，展示各组累计收益走势")}</p>
              <div className="chart-box">
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={groupData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                    <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: "#334155" }}
                      minTickGap={28}
                    />
                    <YAxis
                      tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      width={52}
                    />
                    <Tooltip
                      formatter={(v, name) => [`${(v * 100).toFixed(2)}%`, name]}
                      labelFormatter={(l) => t("日期：{d}", { d: l })}
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid #334155",
                        borderRadius: 8,
                        color: "#e2e8f0",
                      }}
                    />
                    {groupNames.map((g, i) => (
                      <Line
                        key={g}
                        type="monotone"
                        dataKey={g}
                        stroke={GROUP_COLORS[i % GROUP_COLORS.length]}
                        strokeWidth={1.6}
                        dot={false}
                        activeDot={{ r: 3 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {/* 每日盈亏柱状图（正绿负红） */}
          {pnlData.length > 1 && (
            <section className="card">
              <h2>{t("每日盈亏")}</h2>
              <p className="muted">{t("多空组合的逐日收益，正收益绿色、负收益红色")}</p>
              <div className="chart-box">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={pnlData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                    <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: "#334155" }}
                      minTickGap={28}
                    />
                    <YAxis
                      tickFormatter={(v) => `${(v * 100).toFixed(1)}%`}
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      width={56}
                    />
                    <Tooltip
                      formatter={(v) => [`${(v * 100).toFixed(3)}%`, t("当日盈亏")]}
                      labelFormatter={(l) => t("日期：{d}", { d: l })}
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid #334155",
                        borderRadius: 8,
                        color: "#e2e8f0",
                      }}
                      cursor={{ fill: "#1e293b" }}
                    />
                    <Bar dataKey="pnl" radius={[1, 1, 0, 0]}>
                      {pnlData.map((d, i) => (
                        <Cell key={i} fill={d.pnl >= 0 ? "#34d399" : "#f87171"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          {/* score 分布直方图 */}
          {scoreBins.length > 0 && (
            <section className="card">
              <h2>{t("个股信号分布")}</h2>
              <p className="muted">{t("全周期平均信号在个股间的分布（分桶直方图）")}</p>
              <div className="chart-box">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={scoreBins} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                    <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="range"
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 10 }}
                      tickLine={false}
                      axisLine={{ stroke: "#334155" }}
                      interval="preserveStartEnd"
                      minTickGap={16}
                    />
                    <YAxis
                      allowDecimals={false}
                      stroke="#64748b"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      width={36}
                    />
                    <Tooltip
                      formatter={(v) => [v, t("个股数")]}
                      labelFormatter={(l) => t("信号 ≈ {x}", { x: l })}
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid #334155",
                        borderRadius: 8,
                        color: "#e2e8f0",
                      }}
                      cursor={{ fill: "#1e293b" }}
                    />
                    <Bar dataKey="count" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}
        </>
      )}

      {/* 底部操作 */}
      <section className="detail-actions">
        {sub.status === "success" && (
          <Link
            to={`/compare?submissionId1=${sub.id}`}
            className="btn btn-primary"
          >
            {t("🔍 对比此策略")}
          </Link>
        )}
        {team ? (
          <button className="btn" onClick={() => setShowSource(true)}>
            {t("查看源代码")}
          </button>
        ) : (
          <Link to="/login" className="btn">{t("登录后查看源代码")}</Link>
        )}
        <Link to="/leaderboard" className="btn">{t("返回排行榜")}</Link>
      </section>

      {/* 源代码弹窗（需登录） */}
      {showSource && team && <SourceModal id={sub.id} onClose={() => setShowSource(false)} />}

      {/* 原始错误弹窗 */}
      {showRaw && (
        <div className="modal-backdrop" onClick={() => setShowRaw(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>{t("原始错误 #{id}", { id: sub.id })}</h3>
              <button className="btn btn-sm" onClick={() => setShowRaw(false)}>✕</button>
            </div>
            <pre className="code-block">{rawError}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

// 源代码弹窗组件
function SourceModal({ id, onClose }) {
  const { t } = useI18n();
  const [source, setSource] = useState(t("加载中..."));
  useEffect(() => {
    fetch(`/api/submissions/${id}/source`)
      .then((r) => r.text())
      .then(setSource)
      .catch(() => setSource(t("// 加载源代码失败")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{t("源代码 #{id}", { id })}</h3>
          <button className="btn btn-sm" onClick={onClose}>✕</button>
        </div>
        <pre className="code-block">{source}</pre>
      </div>
    </div>
  );
}
