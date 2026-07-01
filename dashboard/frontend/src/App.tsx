import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { useSession } from "./auth/session";
import { Layout } from "./components/Layout";
import { CenteredSpinner } from "./components/ui";
import CommandsPage from "./pages/CommandsPage";
import EmbedBuilderPage from "./pages/EmbedBuilderPage";
import GuildDashboardPage from "./pages/GuildDashboardPage";
import GuildPickerPage from "./pages/GuildPickerPage";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import StaffPage from "./pages/StaffPage";

/** Gate app routes behind a session; unauthenticated users see the login prompt. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { data: session, isLoading } = useSession();
  if (isLoading) return <CenteredSpinner />;
  if (!session) return <LoginPage />;
  return <>{children}</>;
}

/** Gate the staff area behind the bot's owner/staff ids. */
function RequireStaff({ children }: { children: ReactNode }) {
  const { data: session, isLoading } = useSession();
  if (isLoading) return <CenteredSpinner />;
  if (!session) return <LoginPage />;
  if (!session.is_staff) {
    return (
      <div className="container">
        <div className="empty" style={{ marginTop: 40 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🔒</div>
          <div style={{ fontWeight: 700, fontSize: 18, color: "var(--text)" }}>
            Staff only
          </div>
          <p className="muted" style={{ marginTop: 8 }}>
            This area is limited to Miri's bot staff. If that should be you, ask an
            owner to add your Discord id to <span className="mono">STAFF_IDS</span>.
          </p>
          <Link to="/dashboard" className="btn btn--ghost" style={{ marginTop: 16 }}>
            Back to dashboard
          </Link>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Layout>
      <Routes>
        {/* public marketing surface */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/commands" element={<CommandsPage />} />
        <Route path="/embed" element={<EmbedBuilderPage />} />

        {/* the manage-servers app (login required) */}
        <Route path="/dashboard" element={<RequireAuth><GuildPickerPage /></RequireAuth>} />
        <Route
          path="/dashboard/guilds/:guildId"
          element={<RequireAuth><GuildDashboardPage /></RequireAuth>}
        />
        <Route
          path="/dashboard/guilds/:guildId/:moduleKey"
          element={<RequireAuth><GuildDashboardPage /></RequireAuth>}
        />

        {/* bot-staff-only analytics */}
        <Route path="/staff" element={<RequireStaff><StaffPage /></RequireStaff>} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
