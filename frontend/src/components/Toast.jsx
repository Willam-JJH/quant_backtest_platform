// 通知提示系统：ToastProvider + useToast
// 三种类型 success / error / info，3 秒自动消失，点击手动关闭
import { createContext, useCallback, useContext, useRef, useState } from "react";

import { useI18n } from "../i18n.jsx";

const ToastContext = createContext(null);

const ICONS = { success: "✅", error: "❌", info: "💡" };

export function ToastProvider({ children }) {
  const { t } = useI18n();
  const [toasts, setToasts] = useState([]);
  const seqRef = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  // 弹出通知；3 秒后自动消失
  const push = useCallback(
    (type, text) => {
      const id = ++seqRef.current;
      setToasts((list) => [...list, { id, type, text }]);
      setTimeout(() => dismiss(id), 3000);
    },
    [dismiss]
  );

  const api = {
    success: (t) => push("success", t),
    error: (t) => push("error", t),
    info: (t) => push("info", t),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-container" aria-live="polite">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}`}
            onClick={() => dismiss(toast.id)}
            role="status"
          >
            <span>{ICONS[toast.type] ?? "•"}</span>
            <span className="toast-text">{toast.text}</span>
            <button className="toast-close" aria-label={t("关闭")}>✕</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// 供组件弹通知的 Hook
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast 必须在 <ToastProvider> 内使用");
  return ctx;
}
