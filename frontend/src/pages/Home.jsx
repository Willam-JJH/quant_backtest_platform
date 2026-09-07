// 首页 / 仪表盘：统计卡片 + 最近提交 + 排行榜速览 + 快捷导航
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useI18n } from "../i18n.jsx";

// 排行榜速览用的小徽章
const TRACK_LABELS = {
  learning_1: "Learning 1",
  learning_2: "Learning 2",
  learning_3: "Learning 3",
  hidden: "Hidden",
};

export default function Home() {
  const { t } = useI18n();
  // 仪表盘数据
  const [data, setData] = useState(null);
  // 加载 / 错误状态
  const [state, setState] = useState("loading");

  useEffect(() => {
    fetch("/api/dashboard")
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setState("ok");
      })
      .catch(() => setState("error"));
  }, []);

  if (state === "loading") {
    return <div className="home-loading">{t("加载中...")}</div>;
  }

  if (state === "error" || !data) {
    return (
      <div className="card error-card">
        <h2>{t("数据加载失败")}</h2>
        <p>{t("请确认后端已启动（cd backend && python app.py）。")}</p>
      </div>
    );
  }

  return (
    <div className="home">
      {/* 页头 */}
      <section className="home-hero">
        <h1>{t("量化平台")}</h1>
        <p>{t("SickFun 量化课堂 — 提交策略、自动回测、榜单比拼")}</p>
      </section>

      {/* 统计卡片 */}
      <section className="stat-cards">
        <div className="stat-card">
          <div className="stat-value">{data.total_teams}</div>
          <div className="stat-label">{t("队伍数")}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data.total_submissions}</div>
          <div className="stat-label">{t("总提交数")}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">
            {data.leaderboard_summary?.length ?? 0}
          </div>
          <div className="stat-label">{t("赛道数")}</div>
        </div>
      </section>

      <div className="home-grid">
        {/* 最近提交 */}
        <section className="card">
          <h2>{t("最近提交")}</h2>
          {data.recent_submissions?.length ? (
            <table className="table">
              <thead>
                <tr>
                  <th>{t("队伍")}</th>
                  <th>{t("数据轨道")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("分数")}</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_submissions.map((s) => (
                  <tr key={s.id}>
                    <td>{s.team_name}</td>
                    <td>{TRACK_LABELS[s.data_track] ?? s.data_track}</td>
                    <td>
                      <span className={`badge badge-${s.status}`}>{s.status}</span>
                    </td>
                    <td>{s.score ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">{t("还没有提交。")}</p>
          )}
        </section>

        {/* 排行榜速览 */}
        <section className="card">
          <h2>{t("排行榜速览")}</h2>
          {data.leaderboard_summary?.length ? (
            <table className="table">
              <thead>
                <tr>
                  <th>{t("数据轨道")}</th>
                  <th>{t("最高分")}</th>
                  <th>{t("提交数")}</th>
                </tr>
              </thead>
              <tbody>
                {data.leaderboard_summary.map((s) => (
                  <tr key={s.data_track}>
                    <td>{TRACK_LABELS[s.data_track] ?? s.data_track}</td>
                    <td className="score-high">{s.top_score ?? "-"}</td>
                    <td>{s.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">{t("暂无成功评分数据。")}</p>
          )}
        </section>
      </div>

      {/* 快捷导航 */}
      <section className="quick-nav">
        <Link to="/submit" className="quick-card">
          <span className="quick-icon">📤</span>
          <span>{t("提交策略")}</span>
        </Link>
        <Link to="/leaderboard" className="quick-card">
          <span className="quick-icon">🏆</span>
          <span>{t("查看排行榜")}</span>
        </Link>
        <Link to="/downloads" className="quick-card">
          <span className="quick-icon">📥</span>
          <span>{t("下载数据")}</span>
        </Link>
      </section>
    </div>
  );
}
