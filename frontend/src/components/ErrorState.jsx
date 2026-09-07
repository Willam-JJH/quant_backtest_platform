// 错误状态组件：警示图标 + 信息 + 重试按钮
import { useI18n } from "../i18n.jsx";

export default function ErrorState({ message = "数据加载失败", onRetry, contact }) {
  const { t } = useI18n();
  return (
    <div className="error-state">
      <span className="es-icon" aria-hidden="true">⚠️</span>
      <h3>{t(message)}</h3>
      {onRetry && (
        <button className="btn btn-primary" onClick={onRetry}>
          {t("重试")}
        </button>
      )}
      {contact && (
        <p className="muted es-contact">{t("仍无法解决？请联系 {contact}", { contact })}</p>
      )}
    </div>
  );
}
