// 历史记录页面：多条件筛选 + 状态标签 + 源代码弹窗 + 分页
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import StatusBadge from "../components/StatusBadge.jsx";
import Loading from "../components/Loading.jsx";
import ErrorState from "../components/ErrorState.jsx";
import EmptyState from "../components/EmptyState.jsx";
import { useI18n } from "../i18n.jsx";

// 轨道筛选
const TRACK_TABS = [
  { key: null, label: "全部" },
  { key: "learning_1", label: "Learning 1" },
  { key: "learning_2", label: "Learning 2" },
  { key: "learning_3", label: "Learning 3" },
];

// 状态筛选
const STATUS_OPTIONS = [
  { key: null, label: "全部状态" },
  { key: "pending", label: "等待中" },
  { key: "running", label: "进行中" },
  { key: "success", label: "成功" },
  { key: "failed", label: "失败" },
];

// 每页条数
const PAGE_SIZE = 10;

export default function History() {
  const navigate = useNavigate();
  const { t } = useI18n();

  // 筛选条件
  const [teamId, setTeamId] = useState("");
  const [track, setTrack] = useState(null);
  const [status, setStatus] = useState("");
  const [teams, setTeams] = useState([]);

  // 数据 + 分页
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // 源代码弹窗
  const [modalId, setModalId] = useState(null);
  const [source, setSource] = useState("");
  const [sourceLoading, setSourceLoading] = useState(false);

  // 加载队伍列表（供筛选下拉用）
  useEffect(() => {
    fetch("/api/teams")
      .then((r) => r.json())
      .then((d) => setTeams(d.rows || []))
      .catch(() => {});
  }, []);

  // 筛选或翻页变化时请求
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const params = new URLSearchParams();
    params.set("limit", PAGE_SIZE);
    params.set("offset", offset);
    if (teamId) params.set("team_id", teamId);
    if (track) params.set("data_track", track);
    if (status) params.set("status", status);

    fetch(`/api/submissions?${params}`)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled) return;
        setRows(d.rows || []);
        setTotal(d.total_count || 0);
        setError(false);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [teamId, track, status, offset]);

  // 打开源代码弹窗
  async function openSource(id) {
    setModalId(id);
    setSource("");
    setSourceLoading(true);
    try {
      const res = await fetch(`/api/submissions/${id}/source`);
      const text = await res.text();
      setSource(text);
    } catch {
      setSource(t("// 加载源代码失败"));
    } finally {
      setSourceLoading(false);
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="history">
      <h1 className="page-title">📜 {t("历史记录")}</h1>

      {/* 筛选区 */}
      <div className="filters">
        <label className="field">
          <span>{t("队伍")}</span>
          <select value={teamId} onChange={(e) => { setTeamId(e.target.value); setOffset(0); }}>
            <option value="">{t("全部队伍")}</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.display_name}
              </option>
            ))}
          </select>
        </label>

        <div className="tabs filters-tabs">
          {TRACK_TABS.map((tab) => (
            <button
              key={tab.label}
              className={"tab" + (track === tab.key ? " active" : "")}
              onClick={() => { setTrack(tab.key); setOffset(0); }}
            >
              {t(tab.label)}
            </button>
          ))}
        </div>

        <label className="field">
          <span>{t("状态")}</span>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
            {STATUS_OPTIONS.map((s) => (
              <option key={s.label} value={s.key ?? ""}>
                {t(s.label)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* 列表 */}
      {loading ? (
        <Loading text="加载中..." />
      ) : error ? (
        <ErrorState message="加载失败，请确认后端已启动" onRetry={() => setOffset((o) => o)} />
      ) : rows.length === 0 ? (
        <div className="card">
          <EmptyState icon="📭" title="没有符合条件的提交记录" />
        </div>
      ) : (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>{t("提交时间")}</th>
                <th>{t("队伍")}</th>
                <th>{t("数据轨道")}</th>
                <th>{t("状态")}</th>
                <th>{t("分数")}</th>
                <th>{t("操作")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <td className="muted">{s.submitted_at?.slice(0, 16)}</td>
                  <td>{s.team_display_name}</td>
                  <td>
                    <span className="track-chip">{s.data_track}</span>
                  </td>
                  <td><StatusBadge status={s.status} /></td>
                  <td>{s.score ?? "-"}</td>
                  <td className="actions-cell">
                    <button className="btn btn-sm" onClick={() => navigate(`/submission/${s.id}`)}>
                      {t("详情")}
                    </button>
                    <button className="btn btn-sm" onClick={() => openSource(s.id)}>
                      {t("源代码")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* 分页 */}
          <div className="pagination">
            <button
              className="btn btn-sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              {t("← 上一页")}
            </button>
            <span className="muted">
              {t("第 {page} / {pages} 页（共 {count} 条）", {
                page: currentPage,
                pages: pageCount,
                count: total,
              })}
            </span>
            <button
              className="btn btn-sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              {t("下一页 →")}
            </button>
          </div>
        </div>
      )}

      {/* 源代码弹窗 */}
      {modalId && (
        <div className="modal-backdrop" onClick={() => setModalId(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>{t("源代码 #{id}", { id: modalId })}</h3>
              <button className="btn btn-sm" onClick={() => setModalId(null)}>
                ✕
              </button>
            </div>
            <pre className="code-block">
              {sourceLoading ? t("加载中...") : source}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
