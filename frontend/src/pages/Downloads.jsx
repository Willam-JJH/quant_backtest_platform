// 下载中心页面：学习数据 / 策略模板 / 快速开始指南 / 运行环境
import { useEffect, useState } from "react";

import { useI18n } from "../i18n.jsx";

// 字节数格式化（unknownLabel 为“未知大小”的本地化文案）
function fmtSize(bytes, unknownLabel) {
  if (!bytes) return unknownLabel;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function Downloads() {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [state, setState] = useState("loading");

  useEffect(() => {
    fetch("/api/downloads")
      .then((r) => r.json())
      .then((d) => {
        setItems(d.items || []);
        setState("ok");
      })
      .catch(() => setState("error"));
  }, []);

  if (state === "loading") return <div className="home-loading">{t("加载中...")}</div>;
  if (state === "error")
    return (
      <div className="card error-card">
        <h2>{t("加载失败")}</h2>
        <p>{t("请确认后端已启动。")}</p>
      </div>
    );

  return (
    <div className="downloads">
      <h1 className="page-title">📥 {t("下载中心")}</h1>
      <div className="card">
        <table className="table downloads-table">
          <thead>
            <tr>
              <th>{t("资源")}</th>
              <th>{t("说明")}</th>
              <th>{t("大小")}</th>
              <th>{t("操作")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.key}>
                <td className="dl-name">
                  <span className="dl-icon">📦</span>
                  <b>{it.name}</b>
                </td>
                <td className="muted">{it.desc}</td>
                <td>{it.available ? fmtSize(it.size, t("未知大小")) : "—"}</td>
                <td>
                  {it.available ? (
                    <a
                      className="btn btn-primary btn-sm"
                      href={`/api/downloads/${it.filename}`}
                    >
                      {t("下载")}
                    </a>
                  ) : (
                    <span className="muted">{t("敬请期待")}</span>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">{t("暂无资源")}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
