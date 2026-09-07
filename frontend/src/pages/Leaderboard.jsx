// 排行榜页面（核心 🏆）：轨道切换 + 排名表格 + 自动刷新
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import Loading from "../components/Loading.jsx";
import ErrorState from "../components/ErrorState.jsx";
import EmptyState from "../components/EmptyState.jsx";
import { useI18n } from "../i18n.jsx";

// 轨道标签页配置
const TABS = [
  { key: null, label: "全部" },
  { key: "learning_1", label: "Learning 1" },
  { key: "learning_2", label: "Learning 2" },
  { key: "learning_3", label: "Learning 3" },
  { key: "hidden", label: "Hidden" },
];

// 前三名奖牌
const MEDALS = { 1: "🥇", 2: "🥈", 3: "🥉" };

// 把小数格式化成百分比
function pct(v) {
  if (v === null || v === undefined) return "-";
  return `${(v * 100).toFixed(2)}%`;
}

// 分数最大值（用于进度条宽度）
const SCORE_MAX = 100;

export default function Leaderboard() {
  const navigate = useNavigate();
  const { t } = useI18n();
  // 当前选中的轨道
  const [track, setTrack] = useState(null);
  // 排行榜数据
  const [rows, setRows] = useState([]);
  // 加载 / 错误
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  async function load(silent = false) {
    if (!silent) setLoading(true);
    try {
      const q = track ? `?data_track=${track}` : "";
      const res = await fetch(`/api/leaderboard${q}`);
      if (!res.ok) throw new Error("请求失败");
      const data = await res.json();
      setRows(data.rows);
      setError(false);
    } catch {
      setError(true);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  // 切换轨道时重新加载
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [track]);

  // 每 60 秒静默自动刷新（不重置滚动位置、不闪加载动画）
  useEffect(() => {
    const timer = setInterval(() => load(true), 60000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [track]);

  // 加载中
  if (loading) {
    return <Loading text="榜单加载中..." />;
  }

  // 加载失败
  if (error) {
    return <ErrorState message="榜单加载失败，请确认后端已启动" onRetry={() => load()} />;
  }

  return (
    <div className="leaderboard">
      <h1 className="page-title">🏆 {t("排行榜")}</h1>

      {/* 轨道切换标签页 */}
      <div className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.label}
            className={"tab" + (track === tab.key ? " active" : "")}
            onClick={() => setTrack(tab.key)}
          >
            {t(tab.label)}
          </button>
        ))}
      </div>

      {/* 空状态 */}
      {rows.length === 0 ? (
        <div className="card">
          <EmptyState icon="🏆" title="暂无成功评分数据，快去提交你的第一个策略吧！">
            <button className="btn btn-primary" onClick={() => navigate("/submit")}>
              {t("去提交策略")}
            </button>
          </EmptyState>
        </div>
      ) : (
        <div className="card table-card">
          <table className="table leaderboard-table">
            <thead>
              <tr>
                <th>{t("排名")}</th>
                <th>{t("队伍名")}</th>
                <th>{t("数据轨道")}</th>
                <th>{t("综合得分")}</th>
                <th>{t("年化收益")}</th>
                <th>{t("夏普比率")}</th>
                <th>{t("最大回撤")}</th>
                <th>{t("提交时间")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const m = r.metrics || {};
                const medal = MEDALS[r.rank];
                return (
                  <tr
                    key={r.submission_id}
                    className="leaderboard-row"
                    onClick={() => navigate(`/submission/${r.submission_id}`)}
                    title={t("查看详情")}
                  >
                    <td className={`rank-cell${r.rank <= 3 ? " rank-top" : ""}`}>
                      {medal ? `${medal} ${r.rank}` : r.rank}
                    </td>
                    <td className="team-cell">{r.team_display_name}</td>
                    <td>
                      <span className="track-chip">{r.data_track}</span>
                    </td>
                    <td>
                      <div className="score-cell">
                        <span className="score-num">{r.score}</span>
                        <span className="score-bar">
                          <span
                            className="score-bar-fill"
                            style={{ width: `${Math.min((r.score / SCORE_MAX) * 100, 100)}%` }}
                          />
                        </span>
                      </div>
                    </td>
                    <td className={m.annual_return >= 0 ? "pos" : "neg"}>
                      {pct(m.annual_return)}
                    </td>
                    <td>{m.sharpe?.toFixed(2) ?? "-"}</td>
                    <td className="neg">{pct(m.max_drawdown)}</td>
                    <td className="muted">{r.submitted_at?.slice(0, 16)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
