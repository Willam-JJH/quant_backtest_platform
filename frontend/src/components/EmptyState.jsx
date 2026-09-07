// 空数据状态组件：图标 + 文案 + 可选操作
import { useI18n } from "../i18n.jsx";

export default function EmptyState({ icon = "📭", title = "暂无数据", children }) {
  const { t } = useI18n();
  return (
    <div className="empty-state">
      <span className="es-icon" aria-hidden="true">{icon}</span>
      <p>{t(title)}</p>
      {children && <div className="empty-actions">{children}</div>}
    </div>
  );
}
