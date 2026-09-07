// 登录页面：队伍名 + 密码登录，成功后跳转首页
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";

export default function Login() {
  const { team, loading, login } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  // 表单输入
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  // 提交中 / 错误信息
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // 已登录则直接跳首页
  if (!loading && team) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name || !password) {
      setError(t("请输入队名和密码"));
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await login(name, password);
      navigate("/", { replace: true }); // 登录成功跳首页
    } catch (err) {
      setError(err.message || t("登录失败"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={handleSubmit}>
        <h1>{t("队伍登录")}</h1>
        <label className="field">
          <span>{t("队名")}</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("例如：team_alpha")}
            autoComplete="username"
          />
        </label>
        <label className="field">
          <span>{t("密码")}</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("请输入密码")}
            autoComplete="current-password"
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? t("登录中...") : t("登录")}
        </button>
      </form>
    </div>
  );
}
