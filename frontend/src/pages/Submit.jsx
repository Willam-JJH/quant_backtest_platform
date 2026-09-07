// 提交策略页面：队伍/轨道选择 + 拖拽上传 .py（支持批量） + 提交反馈
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import { useToast } from "../components/Toast.jsx";

// 可选数据轨道
const TRACKS = [
  { key: "learning_1", label: "Learning 1" },
  { key: "learning_2", label: "Learning 2" },
  { key: "learning_3", label: "Learning 3" },
];

// 前端文件大小上限提示（1MB）
const MAX_BYTES = 1024 * 1024;

export default function Submit() {
  const { team } = useAuth();
  const { t } = useI18n();
  const toast = useToast();
  const fileInputRef = useRef(null);

  // 队伍列表
  const [teams, setTeams] = useState([]);
  // 表单字段
  const [teamId, setTeamId] = useState("");
  const [track, setTrack] = useState("learning_1");
  // 待提交文件列表：{ file, errors, checking }
  const [entries, setEntries] = useState([]);
  // 拖拽高亮
  const [dragOver, setDragOver] = useState(false);
  // 提交流程状态
  const [phase, setPhase] = useState("idle"); // idle | uploading | success | failed
  const [message, setMessage] = useState("");
  // 批量提交结果 { created: [id,...], count }
  const [batchResult, setBatchResult] = useState(null);

  // 加载队伍列表；已登录则默认选中当前队伍
  useEffect(() => {
    fetch("/api/teams")
      .then((r) => r.json())
      .then((d) => {
        setTeams(d.rows || []);
        if (team) setTeamId(String(team.id));
      })
      .catch(() => {});
  }, [team]);

  // 对单个文件做语法预检查，结果写回对应 entry
  async function checkEntry(entry) {
    try {
      const text = await entry.file.text();
      const res = await fetch("/api/submissions/check", {
        method: "POST",
        headers: { "Content-Type": "text/plain; charset=utf-8" },
        body: text,
      });
      const data = await res.json();
      setEntries((prev) =>
        prev.map((e) =>
          e.file === entry.file
            ? { ...e, errors: data.errors || [], checking: false }
            : e
        )
      );
    } catch {
      // 检查接口异常时不拦截，交给后端回测兜底
      setEntries((prev) =>
        prev.map((e) =>
          e.file === entry.file ? { ...e, errors: [], checking: false } : e
        )
      );
    }
  }

  // 添加一批文件（校验后逐个做语法检查）
  function addFiles(incoming) {
    const list = Array.from(incoming || []);
    const existingNames = new Set(entries.map((e) => e.file.name));
    const accepted = [];
    for (const f of list) {
      if (!f.name.endsWith(".py")) {
        toast.error(t("{name} 不是 .py 文件，已跳过", { name: f.name }));
        continue;
      }
      if (f.size > MAX_BYTES) {
        toast.error(t("{name} 超过 1MB 上限，已跳过", { name: f.name }));
        continue;
      }
      if (existingNames.has(f.name)) {
        toast.error(t("{name} 已在列表中，已跳过", { name: f.name }));
        continue;
      }
      existingNames.add(f.name);
      accepted.push(f);
    }
    if (accepted.length === 0) return;

    const newEntries = accepted.map((f) => ({ file: f, errors: [], checking: true }));
    setEntries((prev) => [...prev, ...newEntries]);
    newEntries.forEach((entry) => checkEntry(entry));
  }

  function removeEntry(file) {
    setEntries((prev) => prev.filter((e) => e.file !== file));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!teamId) {
      setPhase("failed");
      setMessage(t("请选择队伍"));
      return;
    }
    if (entries.length === 0) {
      setPhase("failed");
      setMessage(t("请至少选择一个 .py 策略文件"));
      return;
    }
    if (entries.some((e) => e.checking)) {
      setPhase("failed");
      setMessage(t("仍有文件正在检查语法，请稍候再提交"));
      return;
    }
    const bad = entries.filter((e) => e.errors.length > 0);
    if (bad.length > 0) {
      setPhase("failed");
      setMessage(
        t("{names} 存在语法错误，请修正后再提交", {
          names: bad.map((e) => e.file.name).join("、"),
        })
      );
      return;
    }

    setPhase("uploading");
    const form = new FormData();
    form.append("team_id", teamId);
    form.append("data_track", track);
    entries.forEach((e) => form.append("files", e.file));

    try {
      const res = await fetch("/api/submissions/batch", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) {
        const msg = data.detail || t("提交失败");
        setPhase("failed");
        setMessage(msg);
        toast.error(msg);
        return;
      }
      setPhase("success");
      setBatchResult(data);
      toast.success(t("批量提交成功：{count} 个文件已进入评分队列", { count: data.count }));
      setEntries([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch {
      setPhase("failed");
      setMessage(t("网络错误，请稍后再试"));
      toast.error(t("网络错误，请稍后再试"));
    }
  }

  return (
    <div className="submit-page">
      <h1 className="page-title">{t("📤 提交策略")}</h1>

      <div className="submit-grid">
        {/* 左：提交表单 */}
        <form className="card submit-form" onSubmit={handleSubmit}>
          {/* 队伍选择 */}
          <label className="field">
            <span>{t("队伍")}</span>
            <select value={teamId} onChange={(e) => setTeamId(e.target.value)}>
              <option value="">{t("-- 请选择队伍 --")}</option>
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.display_name}（{team.name}）
                </option>
              ))}
            </select>
          </label>

          {/* 数据轨道选择 */}
          <label className="field">
            <span>{t("数据轨道")}</span>
            <select value={track} onChange={(e) => setTrack(e.target.value)}>
              {TRACKS.map((trackItem) => (
                <option key={trackItem.key} value={trackItem.key}>
                  {trackItem.label}
                </option>
              ))}
            </select>
          </label>

          {/* 文件上传区（支持多选/多文件拖拽） */}
          <div className="field">
            <span>{t("策略文件（可多选批量提交）")}</span>
            <div
              className={
                "dropzone" + (dragOver ? " over" : "") + (entries.length ? " has" : "")
              }
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                addFiles(e.dataTransfer.files);
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".py"
                multiple
                hidden
                onChange={(e) => addFiles(e.target.files)}
              />
              {entries.length > 0 ? (
                <div className="dropzone-file">
                  <span className="dz-icon">🐍</span>
                  <span>{t("已选 {count} 个文件", { count: entries.length })}</span>
                  <span className="muted">{t("（点击可继续添加）")}</span>
                </div>
              ) : (
                <div className="dropzone-hint">
                  <span className="dz-icon">📂</span>
                  <p>{t("点击选择或拖拽 .py 文件到此处（支持多选）")}</p>
                  <p className="muted">{t("每个文件不超过 1MB")}</p>
                </div>
              )}
            </div>

            {/* 已选文件清单 + 逐文件语法检查结果 */}
            {entries.length > 0 && (
              <ul className="file-list">
                {entries.map((e) => (
                  <li key={e.file.name} className="file-item">
                    <div className="file-item-head">
                      <span className="file-name">🐍 {e.file.name}</span>
                      <span className="muted">（{(e.file.size / 1024).toFixed(1)} KB）</span>
                      <button
                        type="button"
                        className="file-remove"
                        onClick={() => removeEntry(e.file)}
                      >
                        ✕ {t("移除")}
                      </button>
                    </div>
                    {e.checking ? (
                      <p className="muted">{t("🔍 正在检查语法…")}</p>
                    ) : e.errors.length > 0 ? (
                      <div className="syntax-errors">
                        {e.errors.map((err, i) => (
                          <div key={i} className="syntax-err">
                            <span className="syntax-line">
                              {t("第 {line} 行", { line: err.line || "?" })}
                            </span>
                            <span className="syntax-msg">{err.msg}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="form-ok">{t("✅ 语法检查通过")}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* 提示信息 */}
          {phase === "failed" && <p className="form-error">⚠️ {message}</p>}
          {phase === "success" && batchResult && (
            <div className="form-ok">
              <p>{t("🎉 批量提交成功！共 {count} 个文件：", { count: batchResult.count })}</p>
              <ul>
                {batchResult.created.map((id) => (
                  <li key={id}>
                    <Link to={`/submission/${id}`}>{t("查看 #{id} →", { id })}</Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            className="btn btn-primary btn-block"
            disabled={phase === "uploading" || entries.some((e) => e.checking)}
          >
            {phase === "uploading"
              ? t("⏳ 上传评分中...")
              : entries.some((e) => e.checking)
              ? t("🔍 语法检查中...")
              : t("提交策略") +
                (entries.length > 1 ? t("（{count} 个）", { count: entries.length }) : "")}
          </button>
        </form>

        {/* 右：提交规则说明 */}
        <aside className="card rules-card">
          <h2>{t("提交规则说明")}</h2>
          <ul className="rules-list">
            <li>
              {t("策略文件必须包含")} <code>generate_signals(data, date)</code> {t("函数。")}
            </li>
            <li>
              {t("该函数接收")} <code>data</code>（{t("数据")}）{t("与")} <code>date</code>（{t("日期")}），{t("返回各股票的信号值。")}
            </li>
            <li>{t("仅接受")} <code>.py</code> {t("文件，每个文件不超过 1MB。")}</li>
            <li>{t("支持一次选择多个文件批量提交，每个文件会独立回测评分。")}</li>
            <li>{t("三个学习轨道使用公开的课堂数据，Hidden 轨道用于正式评分。")}</li>
            <li>{t("提交后系统会自动跑回测并计算收益 / 夏普 / 回撤等指标。")}</li>
          </ul>
        </aside>
      </div>
    </div>
  );
}
