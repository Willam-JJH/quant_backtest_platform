// 根组件：全局认证 + 全局通知 + 路由 + 导航栏 + 页脚
import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./auth.jsx";
import { I18nProvider } from "./i18n.jsx";
import { ToastProvider } from "./components/Toast.jsx";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import AppRoutes from "./routes.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <I18nProvider>
        <AuthProvider>
          <ToastProvider>
            <Navbar />
            <main className="container">
              <AppRoutes />
            </main>
            <Footer />
          </ToastProvider>
        </AuthProvider>
      </I18nProvider>
    </BrowserRouter>
  );
}
