import React from "react";
import ReactDOM from "react-dom/client";
import { MotionConfig } from "framer-motion";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { AuthProvider, RequireAuth, useAuth } from "./auth";
import AppShell from "./components/AppShell";
import Analytics from "./pages/Analytics";
import Dashboard from "./pages/Dashboard";
import ImageStudio from "./pages/ImageStudio";
import Overview from "./pages/Overview";
import Published from "./pages/Published";
import Settings from "./pages/Settings";
import Verification from "./pages/Verification";
import Forgot from "./pages/Forgot";
import GuidePage from "./pages/Guide";
import KnowledgeBase from "./pages/KnowledgeBase";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Multilingual from "./pages/Multilingual";
import ScreenshotStudio from "./pages/ScreenshotStudio";
import VideoStudio from "./pages/VideoStudio";
import NewGuide from "./pages/NewGuide";
import Player from "./pages/Player";
import Register from "./pages/Register";
import Reset from "./pages/Reset";
import { ThemeProvider } from "./theme";

/** Signed-in people go to their guides; everyone else to sign in. */
function Start() {
  const { user } = useAuth();
  if (user === undefined) return null;
  return user ? <Navigate to="/app" replace /> : <Landing />;
}

/** Sign-in pages send people who are already signed in straight to their guides. */
function GuestOnly({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (user === undefined) return null;
  return user ? <Navigate to="/app" replace /> : <>{children}</>;
}

const inApp = (page: React.ReactNode) => (
  <RequireAuth>
    <AppShell>{page}</AppShell>
  </RequireAuth>
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* Framer Motion follows the reader's reduced-motion setting everywhere. */}
    <MotionConfig reducedMotion="user">
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Start />} />
            <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
            <Route path="/register" element={<GuestOnly><Register /></GuestOnly>} />
            <Route path="/forgot" element={<Forgot />} />
            <Route path="/reset" element={<Reset />} />
            <Route path="/app" element={inApp(<Overview />)} />
            <Route path="/app/new" element={inApp(<NewGuide />)} />
            <Route path="/app/guides" element={inApp(<Dashboard />)} />
            <Route path="/app/images" element={inApp(<ImageStudio />)} />
            <Route path="/app/verify" element={inApp(<Verification />)} />
            <Route path="/app/published" element={inApp(<Published />)} />
            <Route path="/app/analytics" element={inApp(<Analytics />)} />
            <Route path="/app/screenshots" element={inApp(<ScreenshotStudio />)} />
            <Route path="/app/video" element={inApp(<VideoStudio />)} />
            <Route path="/app/knowledge" element={inApp(<KnowledgeBase />)} />
            <Route path="/app/languages" element={inApp(<Multilingual />)} />
            <Route path="/app/settings" element={inApp(<Settings />)} />
            <Route path="/app/guides/:id" element={inApp(<GuidePage />)} />
            <Route path="/play/:id" element={<Player />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
    </MotionConfig>
  </React.StrictMode>,
);
