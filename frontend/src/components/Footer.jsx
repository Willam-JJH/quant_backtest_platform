// 页脚：版权、版本号、友情链接
import { Link } from "react-router-dom";

import { useI18n } from "../i18n.jsx";

export default function Footer() {
  const { t } = useI18n();
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-inner">
          <span>{t("© 2026 SickFun 量化平台 · 用 AI 从零搭建")}</span>
          <div className="footer-links">
            <Link to="/downloads">{t("下载中心")}</Link>
            <Link to="/admin">{t("管理后台")}</Link>
            <span className="footer-version">v0.1.0</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
