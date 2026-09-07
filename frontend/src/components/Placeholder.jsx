// 通用占位页：用于尚未实现的页面（后续步骤会逐个替换为真实页面）
import { useI18n } from "../i18n.jsx";

export default function Placeholder({ title }) {
  const { t } = useI18n();
  return (
    <div className="placeholder">
      <h1>{title}</h1>
      <p className="placeholder-note">{t("该页面将在后续步骤实现。")}</p>
    </div>
  );
}
