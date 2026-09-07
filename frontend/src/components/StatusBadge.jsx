// 状态标签组件：success / failed / running / pending
import { useI18n } from "../i18n.jsx";

const STATUS_META = {
  success: { cls: "success", icon: "✅", label: "成功" },
  failed: { cls: "failed", icon: "❌", label: "失败" },
  running: { cls: "running", icon: "⟳", label: "进行中" },
  pending: { cls: "pending", icon: "⏳", label: "等待中" },
};

export default function StatusBadge({ status }) {
  const { t } = useI18n();
  const meta = STATUS_META[status] ?? {
    cls: "pending",
    icon: "•",
    label: status,
  };
  return (
    <span className={`badge badge-${meta.cls}`}>
      <span className={meta.cls === "running" ? "spin" : ""}>{meta.icon}</span>{" "}
      {t(meta.label)}
    </span>
  );
}
