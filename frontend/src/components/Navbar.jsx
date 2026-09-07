// 导航栏：Logo、主导航链接、右侧登录状态、移动端汉堡菜单
import { useState } from "react";
import { NavLink, Link } from "react-router-dom";

import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";

// 主导航链接
const LINKS = [
  { to: "/", label: "首页", end: true },
  { to: "/leaderboard", label: "排行榜" },
  { to: "/submit", label: "提交策略" },
  { to: "/history", label: "历史记录" },
  { to: "/downloads", label: "下载中心" },
];

export default function Navbar() {
  // 移动端菜单开合状态
  const [open, setOpen] = useState(false);
  // 登录状态（来自 AuthContext）
  const { team, logout } = useAuth();
  // 语言切换（来自 I18nContext）
  const { lang, t, toggleLang } = useI18n();

  function handleLogout() {
    logout();
    setOpen(false);
  }

  // 语言切换按钮：显示将切换到的语言
  const langButton = (
    <button
      className="btn btn-sm"
      onClick={toggleLang}
      title={t("切换语言")}
      aria-label={t("切换语言")}
    >
      🌐 {lang === "zh" ? "EN" : "中文"}
    </button>
  );

  return (
    <header className="navbar">
      <div className="navbar-inner">
        {/* Logo */}
        <Link to="/" className="navbar-logo" onClick={() => setOpen(false)}>
          <span className="navbar-logo-mark">量</span>
          <span>{t("量化平台")}</span>
        </Link>

        {/* 桌面端导航 */}
        <nav className="navbar-links">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
            >
              {t(l.label)}
            </NavLink>
          ))}
        </nav>

        {/* 右侧：语言切换 + 登录状态 */}
        <div className="navbar-right">
          {langButton}
          {team ? (
            <div className="navbar-user">
              <span className="navbar-team">👤 {team.display_name}</span>
              <button className="btn btn-sm" onClick={handleLogout}>
                {t("登出")}
              </button>
            </div>
          ) : (
            <Link to="/login" className="btn btn-primary btn-sm">
              {t("登录")}
            </Link>
          )}
        </div>

        {/* 汉堡按钮（移动端） */}
        <button
          className="navbar-burger"
          aria-label={t("菜单")}
          onClick={() => setOpen((v) => !v)}
        >
          <span /> <span /> <span />
        </button>
      </div>

      {/* 移动端展开菜单 */}
      {open && (
        <nav className="navbar-mobile">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
              onClick={() => setOpen(false)}
            >
              {t(l.label)}
            </NavLink>
          ))}
          {team ? (
            <span className="nav-link navbar-team" onClick={handleLogout}>
              {t("登出（{name}）", { name: team.display_name })}
            </span>
          ) : (
            <NavLink to="/login" className="nav-link" onClick={() => setOpen(false)}>
              {t("登录")}
            </NavLink>
          )}
          {langButton}
        </nav>
      )}
    </header>
  );
}
