import type { ReactNode } from "react";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useSession } from "./auth/session";
import { Layout } from "./components/Layout";
import { CenteredSpinner } from "./components/ui";
import { pageTransition } from "./lib/motion";
import GuildDashboardPage from "./pages/GuildDashboardPage";
import GuildPickerPage from "./pages/GuildPickerPage";
import LoginPage from "./pages/LoginPage";

export default function App() {
  const { data: session, isLoading } = useSession();
  const location = useLocation();

  // Coarse transition key: swap between top-level views (loading → login →
  // picker → a given guild) animates, but navigating *between modules* of the
  // same guild keeps the same key, so the dashboard doesn't remount — the panel
  // cross-fade + sliding nav indicator handle intra-guild motion instead.
  const seg = location.pathname.split("/").filter(Boolean);
  let key: string;
  let content: ReactNode;
  if (isLoading) {
    key = "loading";
    content = <CenteredSpinner />;
  } else if (!session) {
    key = "login";
    content = <LoginPage />;
  } else {
    key = seg[0] === "guilds" ? `guild:${seg[1] ?? ""}` : "picker";
    content = (
      <Routes location={location}>
        <Route path="/" element={<GuildPickerPage />} />
        <Route path="/guilds/:guildId" element={<GuildDashboardPage />} />
        <Route path="/guilds/:guildId/:moduleKey" element={<GuildDashboardPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }

  return (
    <MotionConfig reducedMotion="user">
      <Layout>
        <AnimatePresence mode="wait">
          <motion.div
            key={key}
            className="page-viewport"
            variants={pageTransition}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {content}
          </motion.div>
        </AnimatePresence>
      </Layout>
    </MotionConfig>
  );
}
