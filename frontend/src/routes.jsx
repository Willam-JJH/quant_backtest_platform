// 路由配置：将路径映射到页面组件
import { Routes, Route } from "react-router-dom";

import Home from "./pages/Home.jsx";
import Login from "./pages/Login.jsx";
import Submit from "./pages/Submit.jsx";
import Leaderboard from "./pages/Leaderboard.jsx";
import History from "./pages/History.jsx";
import SubmissionDetail from "./pages/SubmissionDetail.jsx";
import Compare from "./pages/Compare.jsx";
import Downloads from "./pages/Downloads.jsx";
import Admin from "./pages/Admin.jsx";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/submit" element={<Submit />} />
      <Route path="/leaderboard" element={<Leaderboard />} />
      <Route path="/history" element={<History />} />
      <Route path="/submission/:submissionId" element={<SubmissionDetail />} />
      <Route path="/compare" element={<Compare />} />
      <Route path="/downloads" element={<Downloads />} />
      <Route path="/admin" element={<Admin />} />
    </Routes>
  );
}
