// 全局登录状态管理：AuthProvider + useAuth
// 用 Context 向全应用共享 token / 队伍信息 / login / logout
import { createContext, useContext, useEffect, useState } from "react";

import { useI18n } from "./i18n.jsx";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const { t } = useI18n();
  // token 初始化自 localStorage
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  // 队伍信息
  const [team, setTeam] = useState(null);
  // 是否正在校验登录态
  const [loading, setLoading] = useState(true);

  // 挂载时用 token 向后端确认登录态
  useEffect(() => {
    let cancelled = false;
    async function check() {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const res = await fetch("/api/session", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) setTeam(data.team);
        } else {
          // token 失效则清理
          localStorage.removeItem("token");
          if (!cancelled) setToken(null);
        }
      } catch {
        // 网络错误：保持现状，不打断浏览
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    check();
    return () => {
      cancelled = true;
    };
  }, [token]);

  // 登录：调用后端并保存 token
  async function login(name, password) {
    const res = await fetch("/api/session/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || t("登录失败"));
    }
    localStorage.setItem("token", data.token);
    setToken(data.token);
    setTeam(data.team);
    return data.team;
  }

  // 登出：清除 token 与队伍信息
  async function logout() {
    try {
      await fetch("/api/session/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      // 忽略登出接口失败，前端照样清理
    }
    localStorage.removeItem("token");
    setToken(null);
    setTeam(null);
  }

  return (
    <AuthContext.Provider value={{ token, team, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// 供组件读取登录态的 Hook
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 <AuthProvider> 内使用");
  return ctx;
}
