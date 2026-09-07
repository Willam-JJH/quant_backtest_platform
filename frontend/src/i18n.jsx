// 国际化：中英文切换
// I18nProvider + useI18n + 英文翻译表（中文原文作为 key）
// 中文模式下 t(key) 原样返回；英文模式下查表，缺失则回退中文。
import { createContext, useContext, useEffect, useState } from "react";

// ── 让所有 API 请求自动携带当前语言（供后端按语言返回文案）──
// 每次请求实时读 localStorage（setLang 已先写入），不依赖 React 上下文时序；
// 带 if 保护避免 Vite HMR 下重复包裹 fetch。
if (typeof window !== "undefined" && !window.__QP_LANG_FETCH__) {
  window.__QP_LANG_FETCH__ = true;
  const _origFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const headers = new Headers(init.headers);
    if (!headers.has("X-Lang")) {
      let lang;
      try {
        lang = localStorage.getItem("lang") === "en" ? "en" : "zh";
      } catch {
        lang = "zh";
      }
      headers.set("X-Lang", lang);
    }
    return _origFetch(input, { ...init, headers });
  };
}

const I18nContext = createContext(null);

// 英文翻译表：中文原文 → 英文
// 含 {name} 形式的占位符，由 t(key, params) 做插值替换。
const EN = {
  // ── 通用 ──
  "加载中...": "Loading...",
  "加载失败": "Failed to load",
  "数据加载失败": "Failed to load data",
  "网络错误": "Network error",
  "网络错误，请稍后再试": "Network error, please try again later",
  "重试": "Retry",
  "删除": "Delete",
  "详情": "Details",
  "暂无数据": "No data",
  "该页面将在后续步骤实现。": "This page will be implemented in a later step.",
  "关闭": "Close",
  "仍无法解决？请联系 {contact}": "Still stuck? Contact {contact}",

  // ── 导航栏 / 页脚 ──
  "首页": "Home",
  "排行榜": "Leaderboard",
  "提交策略": "Submit Strategy",
  "历史记录": "History",
  "下载中心": "Downloads",
  "量化平台": "Quant Platform",
  "登出": "Log out",
  "登录": "Log in",
  "登出（{name}）": "Log out ({name})",
  "菜单": "Menu",
  "切换语言": "Switch language",
  "© 2026 SickFun 量化平台 · 用 AI 从零搭建":
    "© 2026 SickFun Quant Platform · Built from scratch with AI",
  "管理后台": "Admin",

  // ── 状态徽章 ──
  "成功": "Success",
  "失败": "Failed",
  "进行中": "Running",
  "等待中": "Pending",

  // ── 登录页 ──
  "队伍登录": "Team Login",
  "队名": "Team name",
  "密码": "Password",
  "例如：team_alpha": "e.g. team_alpha",
  "请输入密码": "Enter password",
  "请输入队名和密码": "Please enter team name and password",
  "登录失败": "Login failed",
  "登录中...": "Logging in...",

  // ── 首页 ──
  "请确认后端已启动（cd backend && python app.py）。":
    "Please make sure the backend is running (cd backend && python app.py).",
  "SickFun 量化课堂 — 提交策略、自动回测、榜单比拼":
    "SickFun Quant Classroom — submit strategies, auto-backtest, compete on the leaderboard",
  "队伍数": "Teams",
  "总提交数": "Total Submissions",
  "赛道数": "Tracks",
  "最近提交": "Recent Submissions",
  "队伍": "Team",
  "数据轨道": "Data Track",
  "状态": "Status",
  "分数": "Score",
  "还没有提交。": "No submissions yet.",
  "排行榜速览": "Leaderboard Overview",
  "最高分": "Top Score",
  "提交数": "Submissions",
  "暂无成功评分数据。": "No scored data yet.",
  "查看排行榜": "View Leaderboard",
  "下载数据": "Download Data",

  // ── 提交页 ──
  "{name} 不是 .py 文件，已跳过": "{name} is not a .py file, skipped",
  "{name} 超过 1MB 上限，已跳过": "{name} exceeds the 1MB limit, skipped",
  "{name} 已在列表中，已跳过": "{name} is already in the list, skipped",
  "请选择队伍": "Please select a team",
  "请至少选择一个 .py 策略文件": "Please select at least one .py strategy file",
  "仍有文件正在检查语法，请稍候再提交":
    "Some files are still being checked, please wait before submitting",
  "{names} 存在语法错误，请修正后再提交":
    "{names} has syntax errors, please fix them before submitting",
  "提交失败": "Submission failed",
  "批量提交成功：{count} 个文件已进入评分队列":
    "Batch submit successful: {count} file(s) queued for scoring",
  "📤 提交策略": "📤 Submit Strategy",
  "-- 请选择队伍 --": "-- Select a team --",
  "策略文件（可多选批量提交）": "Strategy files (multiple allowed)",
  "已选 {count} 个文件": "{count} file(s) selected",
  "（点击可继续添加）": "(click to add more)",
  "点击选择或拖拽 .py 文件到此处（支持多选）":
    "Click or drag .py files here (multiple allowed)",
  "每个文件不超过 1MB": "Each file ≤ 1MB",
  "移除": "Remove",
  "🔍 正在检查语法…": "🔍 Checking syntax...",
  "第 {line} 行": "Line {line}",
  "✅ 语法检查通过": "✅ Syntax check passed",
  "🎉 批量提交成功！共 {count} 个文件：":
    "🎉 Batch submit successful! {count} file(s):",
  "查看 #{id} →": "View #{id} →",
  "⏳ 上传评分中...": "⏳ Uploading...",
  "🔍 语法检查中...": "🔍 Checking syntax...",
  "（{count} 个）": "({count} files)",
  "提交规则说明": "Submission Rules",
  "策略文件必须包含": "The strategy file must contain",
  "函数。": "function.",
  "该函数接收": "This function takes",
  "数据": "data",
  "与": "and",
  "日期": "date",
  "返回各股票的信号值。": "and returns a signal value for each stock.",
  "仅接受": "Only",
  "文件，每个文件不超过 1MB。": "files are accepted, each ≤ 1MB.",
  "支持一次选择多个文件批量提交，每个文件会独立回测评分。":
    "Select multiple files for batch submission; each file is backtested and scored independently.",
  "三个学习轨道使用公开的课堂数据，Hidden 轨道用于正式评分。":
    "The three learning tracks use public classroom data; the Hidden track is for official scoring.",
  "提交后系统会自动跑回测并计算收益 / 夏普 / 回撤等指标。":
    "After submission the system auto-runs backtests and computes return / Sharpe / drawdown metrics.",

  // ── 排行榜页 ──
  "全部": "All",
  "榜单加载中...": "Loading leaderboard...",
  "榜单加载失败，请确认后端已启动":
    "Failed to load leaderboard, please make sure the backend is running",
  "🏆 排行榜": "🏆 Leaderboard",
  "暂无成功评分数据，快去提交你的第一个策略吧！":
    "No scored data yet — submit your first strategy!",
  "去提交策略": "Go submit",
  "排名": "Rank",
  "队伍名": "Team",
  "综合得分": "Score",
  "年化收益": "Annual Return",
  "夏普比率": "Sharpe Ratio",
  "最大回撤": "Max Drawdown",
  "提交时间": "Submitted At",
  "查看详情": "View details",

  // ── 历史记录页 ──
  "📜 历史记录": "📜 History",
  "全部状态": "All statuses",
  "全部队伍": "All teams",
  "加载失败，请确认后端已启动":
    "Failed to load, please make sure the backend is running",
  "没有符合条件的提交记录": "No submissions match the filter",
  "操作": "Actions",
  "源代码": "Source",
  "← 上一页": "← Prev",
  "下一页 →": "Next →",
  "第 {page} / {pages} 页（共 {count} 条）": "Page {page} / {pages} ({count} total)",
  "源代码 #{id}": "Source #{id}",
  "// 加载源代码失败": "// Failed to load source",

  // ── 提交详情页 ──
  "年化收益率": "Annual Return",
  "策略年度化收益率": "Annualized strategy return",
  "单位风险的超额收益": "Excess return per unit of risk",
  "区间内最大亏损幅度": "Max loss over the period",
  "波动率": "Volatility",
  "年化收益波动": "Annualized return volatility",
  "胜率": "Win Rate",
  "盈利天数占比": "Share of profitable days",
  "累计收益": "Cumulative Return",
  "回测期累计收益率": "Cumulative return over the backtest",
  "日收益标准差": "Daily Return Std",
  "单日收益离散程度": "Dispersion of daily returns",
  "提交不存在": "Submission not found",
  "返回历史记录": "Back to History",
  "📊 提交详情 #{id}": "📊 Submission Detail #{id}",
  "队伍：": "Team:",
  "提交于 {time}": "Submitted at {time}",
  "评分于 {time}": "Scored at {time}",
  "❌ 本次评分失败": "❌ Scoring failed",
  "无错误信息": "No error message",
  "查看原始错误": "View raw error",
  "📌 多空候选股": "📌 Long/Short Candidates",
  "全周期平均信号最高者为多头候选，最低者为空头候选":
    "Highest average signal = long candidates, lowest = short",
  "🟢 多头 Top {n}": "🟢 Long Top {n}",
  "🔴 空头 Bottom {n}": "🔴 Short Bottom {n}",
  "代码": "Code",
  "平均信号": "Avg Signal",
  "指标明细": "Metrics Detail",
  "指标": "Metric",
  "数值": "Value",
  "说明": "Description",
  "暂无明细指标": "No metrics available",
  "累计收益率": "Cumulative Return",
  "日期：{d}": "Date: {d}",
  "收益曲线数据生成中…": "Generating return curve...",
  "分组累计收益": "Grouped Cumulative Return",
  "信号由低到高分为 5 组，展示各组累计收益走势":
    "Signals split into 5 groups from low to high, showing each group's cumulative return",
  "每日盈亏": "Daily P&L",
  "多空组合的逐日收益，正收益绿色、负收益红色":
    "Daily long/short portfolio return; green = gain, red = loss",
  "当日盈亏": "Daily P&L",
  "个股信号分布": "Stock Signal Distribution",
  "全周期平均信号在个股间的分布（分桶直方图）":
    "Distribution of average signals across stocks (binned histogram)",
  "个股数": "Stocks",
  "信号 ≈ {x}": "Signal ≈ {x}",
  "🔍 对比此策略": "🔍 Compare this strategy",
  "查看源代码": "View source",
  "登录后查看源代码": "Log in to view source",
  "返回排行榜": "Back to Leaderboard",
  "原始错误 #{id}": "Raw Error #{id}",
  "无法获取原始错误": "Unable to fetch raw error",

  // ── 对比页 ──
  "对比失败": "Comparison failed",
  "🔍 策略对比": "🔍 Strategy Comparison",
  "策略 A": "Strategy A",
  "策略 B": "Strategy B",
  "-- 请选择策略 A --": "-- Select strategy A --",
  "-- 请选择策略 B --": "-- Select strategy B --",
  "请选择两个策略进行对比": "Select two strategies to compare",
  "请再选择一个策略进行对比": "Select one more strategy to compare",
  "对比中...": "Comparing...",
  "登录可查看源码": "Log in to view source",
  "指标对比与差异（A − B）": "Metric Comparison & Difference (A − B)",
  "差异": "Difference",

  // ── 下载中心页 ──
  "未知大小": "Unknown size",
  "请确认后端已启动。": "Please make sure the backend is running.",
  "📥 下载中心": "📥 Downloads",
  "资源": "Resource",
  "大小": "Size",
  "下载": "Download",
  "敬请期待": "Coming soon",
  "暂无资源": "No resources",

  // ── 管理后台页 ──
  "校验登录...": "Verifying login...",
  "🛠️ 管理后台": "🛠️ Admin",
  "退出管理员": "Sign out",
  "队伍管理": "Teams",
  "提交管理": "Submissions",
  "平台配置": "Settings",
  "管理员登录": "Admin Login",
  "管理员密码": "Admin password",
  "密码错误": "Wrong password",
  "请求失败 ({status})": "Request failed ({status})",
  "加载队伍失败": "Failed to load teams",
  "队伍已创建": "Team created",
  "确认删除队伍 #{id} 及其全部提交？": "Delete team #{id} and all its submissions?",
  "已删除": "Deleted",
  "确认批量删除 {count} 个队伍？": "Delete {count} team(s)?",
  "已删除 {count} 个队伍": "Deleted {count} team(s)",
  "创建新队伍": "Create Team",
  "登录名 name": "login name",
  "显示名 display_name": "display name",
  "密码 password": "password",
  "创建": "Create",
  "共 {count} 个队伍": "{count} teams",
  "批量删除所选": "Delete selected",
  "名称": "Name",
  "显示名": "Display name",
  "提交次数": "Submissions",
  "创建时间": "Created",
  "加载提交失败": "Failed to load submissions",
  "确认重新运行提交 #{id}？旧评分将被清空。":
    "Re-run submission #{id}? Its old score will be cleared.",
  "#{id} 已重排": "#{id} requeued",
  "确认删除提交 #{id}？": "Delete submission #{id}?",
  "#{id} 已删除": "#{id} deleted",
  "共 {count} 条提交": "{count} submissions",
  "轨道": "Track",
  "重跑": "Re-run",
  "加载配置失败": "Failed to load settings",
  "平台信息": "Platform Info",
  "应用：": "App:",
  "　版本：": " Version:",
  "数据轨道：": "Data tracks:",
  "队伍总数": "Total teams",
  "提交总数": "Total submissions",
  "各轨道提交统计": "Submissions by track",
  "数量": "Count",
};

// 读取初始语言（localStorage 持久化，默认中文）
function getInitialLang() {
  return localStorage.getItem("lang") === "en" ? "en" : "zh";
}

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(getInitialLang);

  // 切换语言时持久化，并同步 <html lang> 与页面标题
  useEffect(() => {
    localStorage.setItem("lang", lang);
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.title = lang === "zh" ? "量化平台" : "Quant Platform";
  }, [lang]);

  // 翻译函数：中文原样返回；英文查表，缺失回退中文；支持 {name} 插值
  function t(key, params) {
    let text = lang === "en" ? EN[key] ?? key : key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        text = text.split(`{${k}}`).join(String(v));
      }
    }
    return text;
  }

  function toggleLang() {
    setLang((l) => (l === "zh" ? "en" : "zh"));
  }

  return (
    <I18nContext.Provider value={{ lang, setLang, toggleLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

// 供组件读取语言与翻译函数的 Hook
export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n 必须在 <I18nProvider> 内使用");
  return ctx;
}
