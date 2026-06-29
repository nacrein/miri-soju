import { Navigate, Route, Routes } from "react-router-dom";

import { useSession } from "./auth/session";
import { Layout } from "./components/Layout";
import { CenteredSpinner } from "./components/ui";
import GuildDashboardPage from "./pages/GuildDashboardPage";
import GuildPickerPage from "./pages/GuildPickerPage";
import LoginPage from "./pages/LoginPage";

export default function App() {
  const { data: session, isLoading } = useSession();

  return (
    <Layout>
      {isLoading ? (
        <CenteredSpinner />
      ) : !session ? (
        <LoginPage />
      ) : (
        <Routes>
          <Route path="/" element={<GuildPickerPage />} />
          <Route path="/guilds/:guildId" element={<GuildDashboardPage />} />
          <Route path="/guilds/:guildId/:moduleKey" element={<GuildDashboardPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      )}
    </Layout>
  );
}
