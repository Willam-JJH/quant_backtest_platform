// 策略对比页面：并排展示两个策略 + 指标差异 + 可视化对比条
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../auth.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { useI18n } from "../i18n.jsx";

// 系列颜色（经色盲校验：蓝 / 深橙）
const COLOR_A = "#3b82f6";
const COLOR_B = "#ea580c";

// 待对比指标（跨不同量纲，逐项缩放对比）
const COMPARE_METRICS = [
  { key: "score", label: "综合得分", fmt: "num" },
  { key: "annual_return", label: "年化收益率", fmt: "pct" },
  { key: "sharpe", label: "夏普比率", fmt: "num" },
  { key: "max_drawdown", label: "最大回撤", fmt: "pct" },
];

function fmtPct(v) {
  return `${(v * 100).toFixed(2)}%`;
}
function fmtVal(key, v) {
  if (v === null || v === undefined) return "-";
  const num = Number(v);
  if (Number.isNaN(num)) return v;
  const info = COMPARE_METRICS.find((m) => m.key === key);
  return info?.fmt === "pct" ? fmtPct(num) : num.toFixed(2);
}

export default function Compare() {
  const { team } = useAuth();
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  // 从 URL 初始化
  const [aId, setAId] = useState(params.get("submissionId1") || "");
  const [bId, setBId] = useState(params.get("submissionId2") || "");
  // 可选提交
  const [options, setOptions] = useState([]);
  // 对比结果
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 加载可对比列表
  useEffect(() => {
    fetch("/api/compare/options")
      .then((r) => r.json())
      .then((d) => setOptions(d.submissions || []))
      .catch(() => {});
  }, []);

  // 选择变化同步到 URL
  function pick(side, val) {
    const next = new URLSearchParams(params);
    if (side === "a") {
      setAId(val);
      val ? next.set("submissionId1", val) : next.delete("submissionId1");
    } else {
      setBId(val);
      val ? next.set("submissionId2", val) : next.delete("submissionId2");
    }
    setParams(next, { replace: true });
  }

  // 两个都选上后请求对比
  useEffect(() => {
    if (!aId || !bId) {
      setResult(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ submission_ids: [Number(aId), Number(bId)] }),
    })
      .then(async (r) => {
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || t("对比失败"));
        return data;
      })
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [aId, bId]);

  const optionById = (id) => options.find((o) => String(o.id) === String(id));

  return (
    <div className="compare-page">
      <h1 className="page-title">🔍 {t("策略对比")}</h1>

      {/* 双选择器 */}
      <div className="compare-pickers">
        <label className="field">
          <span style={{ color: COLOR_A }}>{t("策略 A")}</span>
          <select value={aId} onChange={(e) => pick("a", e.target.value)}>
            <option value="">{t("-- 请选择策略 A --")}</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
        </label>
        <span className="vs">VS</span>
        <label className="field">
          <span style={{ color: COLOR_B }}>{t("策略 B")}</span>
          <select value={bId} onChange={(e) => pick("b", e.target.value)}>
            <option value="">{t("-- 请选择策略 B --")}</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
        </label>
      </div>

      {/* 引导提示 */}
      {!aId && !bId && (
        <div className="card empty-card"><p className="empty-icon">↔️</p><p>{t("请选择两个策略进行对比")}</p></div>
      )}
      {Boolean(aId) !== Boolean(bId) && (
        <div className="card empty-card"><p className="empty-icon">➡️</p><p>{t("请再选择一个策略进行对比")}</p></div>
      )}

      {loading && <div className="home-loading">{t("对比中...")}</div>}
      {error && (
        <div className="card error-card">
          <p>{error}</p>
          <button className="btn btn-primary" onClick={() => window.location.reload()}>{t("重试")}</button>
        </div>
      )}

      {/* 对比结果 */}
      {result && !loading && !error && (
        <>
          <div className="compare-cards">
            {result.submissions.map((s, idx) => {
              const color = idx === 0 ? COLOR_A : COLOR_B;
              const meta = optionById(s.id);
              return (
                <div className="card compare-card" key={s.id} style={{ borderTop: `3px solid ${color}` }}>
                  <div className="compare-card-head">
                    <span className="compare-team" style={{ color }}>{s.team_display_name}</span>
                    <span className="track-chip">{s.data_track}</span>
                    <StatusBadge status="success" />
                  </div>
                  <div className="compare-score">{s.score}</div>
                  <div className="kpi-label">{t("综合得分")}</div>
                  <div className="muted small">{meta?.label || `#${s.id}`}</div>
                  {!team && <div className="muted small">{t("登录可查看源码")}</div>}
                </div>
              );
            })}
          </div>

          {/* 指标差异明细 + 可视化对比条 */}
          <div className="card compare-detail">
            <h2>{t("指标对比与差异（A − B）")}</h2>
            <table className="table compare-table">
              <thead>
                <tr>
                  <th>{t("指标")}</th>
                  <th style={{ color: COLOR_A }}>{t("策略 A")}</th>
                  <th style={{ color: COLOR_B }}>{t("策略 B")}</th>
                  <th>{t("差异")}</th>
                </tr>
              </thead>
              <tbody>
                {COMPARE_METRICS.map((mk) => {
                  const ma = result.submissions[0].metrics || {};
                  const mb = result.submissions[1].metrics || {};
                  const va = mk.key === "score" ? result.submissions[0].score : ma[mk.key];
                  const vb = mk.key === "score" ? result.submissions[1].score : mb[mk.key];
                  const na = Number(va) || 0;
                  const nb = Number(vb) || 0;
                  // 逐行缩放：以两者绝对值较大者为基准
                  const span = Math.max(Math.abs(na), Math.abs(nb), 0.0001);
                  const delta = result.deltas?.[mk.key];

                  return (
                    <tr key={mk.key}>
                      <td><b>{t(mk.label)}</b></td>
                      <td>
                        <div className="hbar">
                          <span className="hbar-fill" style={{ width: `${(Math.abs(na) / span) * 100}%`, background: COLOR_A }} />
                        </div>
                        <span className="hbar-val">{fmtVal(mk.key, va)}</span>
                      </td>
                      <td>
                        <div className="hbar">
                          <span className="hbar-fill" style={{ width: `${(Math.abs(nb) / span) * 100}%`, background: COLOR_B }} />
                        </div>
                        <span className="hbar-val">{fmtVal(mk.key, vb)}</span>
                      </td>
                      <td>
                        {delta === undefined || delta === null ? (
                          <span className="muted">-</span>
                        ) : (
                          <span className={`delta ${delta > 0 ? "pos" : delta < 0 ? "neg" : "muted"}`}>
                            {delta > 0 ? "▲" : delta < 0 ? "▼" : "＝"}{" "}
                            {mk.fmt === "pct" ? fmtPct(delta) : delta.toFixed(2)}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
