// 加载动画组件：旋转圆环 + 可选文字 + 可选全屏
import { useI18n } from "../i18n.jsx";

export default function Loading({ text = "加载中...", fullscreen = false }) {
  const { t } = useI18n();
  return (
    <div className={"loading" + (fullscreen ? " loading-fullscreen" : "")}>
      <div className="spinner" aria-hidden="true" />
      {text && <p className="loading-text">{t(text)}</p>}
    </div>
  );
}
