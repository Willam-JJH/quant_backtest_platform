// 管理后台页面：管理员登录 + 队伍管理 + 提交管理 + 平台配置
import { useCallback, useEffect, useState } from "react";

import StatusBadge from "../components/StatusBadge.jsx";
import { useI18n } from "../i18n.jsx";

// 读取/保存管理员 token
function getToken() {
  return localStorage.getItem("admin_token") || "";
}

export default function Admin() {
  const { t } = useI18n();
  const [token, setToken] = useState(getToken());
  const [authed, setAuthed] = useState(false);
  // 登录态校验中
  const [checking, setChecking] = useState(true);
  const [tab, setTab] = useState("teams");

  // 校验 token 是否有效（调任意受保护接口，401 即失效）
  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setAuthed(false);
      setChecking(false);
      return;
    }
    fetch("/api/admin/settings", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!cancelled) setAuthed(r.ok);
      })
      .catch(() => {
        if (!cancelled) setAuthed(false);
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  function logout() {
    localStorage.removeItem("admin_token");
    setToken("");
    setAuthed(false);
  }

  if (checking) return <div className="home-loading">{t("校验登录...")}</div>;

  // 未登录 → 管理员登录表单
  if (!authed) return <AdminLogin onOk={(tok) => { setToken(tok); setAuthed(true); }} />;

  return (
    <div className="admin">
      <div className="admin-head">
        <h1 className="page-title">🛠️ {t("管理后台")}</h1>
        <button className="btn btn-sm" onClick={logout}>{t("退出管理员")}</button>
      </div>

      <div className="tabs">
        <button className={"tab" + (tab === "teams" ? " active" : "")} onClick={() => setTab("teams")}>{t("队伍管理")}</button>
        <button className={"tab" + (tab === "subs" ? " active" : "")} onClick={() => setTab("subs")}>{t("提交管理")}</button>
        <button className={"tab" + (tab === "settings" ? " active" : "")} onClick={() => setTab("settings")}>{t("平台配置")}</button>
      </div>

      {tab === "teams" && <TeamsTab token={token} />}
      {tab === "subs" && <SubsTab token={token} />}
      {tab === "settings" && <SettingsTab token={token} />}
    </div>
  );
}

// ── 管理员登录表单 ──
function AdminLogin({ onOk }) {
  const { t } = useI18n();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pw }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || t("密码错误"));
      localStorage.setItem("admin_token", data.token);
      onOk(data.token);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={submit}>
        <h1>{t("管理员登录")}</h1>
        <label className="field">
          <span>{t("管理员密码")}</span>
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} />
        </label>
        {err && <p className="form-error">⚠️ {err}</p>}
        <button className="btn btn-primary btn-block" disabled={busy}>
          {busy ? t("登录中...") : t("登录")}
        </button>
      </form>
    </div>
  );
}

// 通用请求封装：自动带管理员 token
function useAdminApi(token) {
  const { t } = useI18n();
  return useCallback(
    async (url, opts = {}) => {
      const res = await fetch(url, {
        ...opts,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(opts.body ? { "Content-Type": "application/json" } : {}),
        },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || t("请求失败 ({status})", { status: res.status }));
      return data;
    },
    [token, t]
  );
}

// ── 队伍管理 ──
function TeamsTab({ token }) {
  const { t } = useI18n();
  const api = useAdminApi(token);
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [form, setForm] = useState({ name: "", display_name: "", password: "" });
  const [msg, setMsg] = useState({ type: "", text: "" });

  const load = useCallback(() => {
    api("/api/admin/teams")
      .then((d) => setRows(d.rows || []))
      .catch(() => setMsg({ type: "err", text: t("加载队伍失败") }));
  }, [api, t]);

  useEffect(() => {
    load();
  }, [load]);

  function flash(type, s) {
    setMsg({ type, text: s });
    setTimeout(() => setMsg({ type: "", text: "" }), 2500);
  }

  async function createTeam(e) {
    e.preventDefault();
    try {
      await api("/api/admin/teams", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setForm({ name: "", display_name: "", password: "" });
      flash("ok", t("队伍已创建"));
      load();
    } catch (ex) {
      flash("err", ex.message);
    }
  }

  async function delTeam(id) {
    if (!confirm(t("确认删除队伍 #{id} 及其全部提交？", { id }))) return;
    try {
      await api(`/api/admin/teams/${id}`, { method: "DELETE" });
      flash("ok", t("已删除"));
      load();
    } catch (ex) {
      flash("err", ex.message);
    }
  }

  async function bulkDelete() {
    const ids = [...selected];
    if (!ids.length || !confirm(t("确认批量删除 {count} 个队伍？", { count: ids.length }))) return;
    try {
      await api("/api/admin/teams/bulk-action", {
        method: "POST",
        body: JSON.stringify({ action: "delete", ids }),
      });
      flash("ok", t("已删除 {count} 个队伍", { count: ids.length }));
      setSelected(new Set());
      load();
    } catch (ex) {
      flash("err", ex.message);
    }
  }

  function toggle(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <div className="admin-panel">
      {/* 创建队伍 */}
      <form className="card admin-create" onSubmit={createTeam}>
        <h2>{t("创建新队伍")}</h2>
        <div className="admin-create-row">
          <input placeholder={t("登录名 name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <input placeholder={t("显示名 display_name")} value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required />
          <input placeholder={t("密码 password")} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          <button className="btn btn-primary">{t("创建")}</button>
        </div>
      </form>

      {msg.text && (
        <p className={msg.type === "ok" ? "form-ok" : "form-error"}>{msg.text}</p>
      )}

      <div className="card">
        <div className="table-actions">
          <span>{t("共 {count} 个队伍", { count: rows.length })}</span>
          <button className="btn btn-danger btn-sm" disabled={!selected.size} onClick={bulkDelete}>
            {t("批量删除所选")}
          </button>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th><input type="checkbox" checked={selected.size === rows.length && rows.length > 0} onChange={() => setSelected(selected.size === rows.length ? new Set() : new Set(rows.map((r) => r.id)))} /></th>
              <th>ID</th><th>{t("名称")}</th><th>{t("显示名")}</th><th>{t("提交次数")}</th><th>{t("创建时间")}</th><th>{t("操作")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><input type="checkbox" checked={selected.has(r.id)} onChange={() => toggle(r.id)} /></td>
                <td>{r.id}</td>
                <td>{r.name}</td>
                <td>{r.display_name}</td>
                <td>{r.submission_count}</td>
                <td className="muted">{r.created_at?.slice(0, 16)}</td>
                <td><button className="btn btn-danger btn-sm" onClick={() => delTeam(r.id)}>{t("删除")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 提交管理 ──
function SubsTab({ token }) {
  const { t } = useI18n();
  const api = useAdminApi(token);
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState({ type: "", text: "" });

  const load = useCallback(() => {
    api("/api/admin/submissions?limit=100")
      .then((d) => setRows(d.rows || []))
      .catch(() => setMsg({ type: "err", text: t("加载提交失败") }));
  }, [api, t]);

  useEffect(() => {
    load();
  }, [load]);

  function flash(type, s) {
    setMsg({ type, text: s });
    setTimeout(() => setMsg({ type: "", text: "" }), 2500);
  }

  async function rerun(id) {
    if (!confirm(t("确认重新运行提交 #{id}？旧评分将被清空。", { id }))) return;
    try {
      const d = await api("/api/admin/submissions/rerun", {
        method: "POST",
        body: JSON.stringify({ id }),
      });
      flash("ok", d.message || t("#{id} 已重排", { id }));
      load();
    } catch (ex) {
      flash("err", ex.message);
    }
  }

  async function delSub(id) {
    if (!confirm(t("确认删除提交 #{id}？", { id }))) return;
    try {
      await api(`/api/admin/submissions/${id}`, { method: "DELETE" });
      flash("ok", t("#{id} 已删除", { id }));
      load();
    } catch (ex) {
      flash("err", ex.message);
    }
  }

  return (
    <div className="admin-panel">
      {msg.text && <p className={msg.type === "ok" ? "form-ok" : "form-error"}>{msg.text}</p>}
      <div className="card">
        <div className="table-actions"><span>{t("共 {count} 条提交", { count: rows.length })}</span></div>
        <table className="table">
          <thead>
            <tr><th>ID</th><th>{t("队伍")}</th><th>{t("轨道")}</th><th>{t("状态")}</th><th>{t("分数")}</th><th>{t("提交时间")}</th><th>{t("操作")}</th></tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{s.team_display_name}</td>
                <td><span className="track-chip">{s.data_track}</span></td>
                <td><StatusBadge status={s.status} /></td>
                <td>{s.score ?? "-"}</td>
                <td className="muted">{s.submitted_at?.slice(0, 16)}</td>
                <td className="actions-cell">
                  <button className="btn btn-sm" onClick={() => rerun(s.id)}>{t("重跑")}</button>
                  <button className="btn btn-danger btn-sm" onClick={() => delSub(s.id)}>{t("删除")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 平台配置 / 统计 ──
function SettingsTab({ token }) {
  const { t } = useI18n();
  const api = useAdminApi(token);
  const [settings, setSettings] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api("/api/admin/settings")
      .then(setSettings)
      .catch(() => setErr(t("加载配置失败")));
  }, [api, t]);

  if (err) return <div className="card error-card"><p>{err}</p></div>;
  if (!settings) return <div className="home-loading">{t("加载中...")}</div>;

  return (
    <div className="admin-panel">
      <div className="card">
        <h2>{t("平台信息")}</h2>
        <p>{t("应用：")}<b>{settings.app}</b>{t("　版本：")}<b>{settings.version}</b></p>
        <p>{t("数据轨道：")}{settings.data_tracks.join(" / ")}</p>
      </div>
      <div className="stat-cards" style={{ gridTemplateColumns: "repeat(2,1fr)" }}>
        <div className="stat-card"><div className="stat-value">{settings.stats.total_teams}</div><div className="stat-label">{t("队伍总数")}</div></div>
        <div className="stat-card"><div className="stat-value">{settings.stats.total_submissions}</div><div className="stat-label">{t("提交总数")}</div></div>
      </div>
      <div className="card">
        <h2>{t("各轨道提交统计")}</h2>
        <table className="table">
          <thead><tr><th>{t("数据轨道")}</th><th>{t("状态")}</th><th>{t("数量")}</th></tr></thead>
          <tbody>
            {settings.by_track_status.map((r, i) => (
              <tr key={i}>
                <td><span className="track-chip">{r.data_track}</span></td>
                <td><StatusBadge status={r.status} /></td>
                <td>{r.c}</td>
              </tr>
            ))}
            {settings.by_track_status.length === 0 && <tr><td colSpan={3} className="muted">{t("暂无数据")}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
