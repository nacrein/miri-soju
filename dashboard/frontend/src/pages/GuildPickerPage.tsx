import { useNavigate } from "react-router-dom";

import { useSession } from "../auth/session";
import { GuildIcon } from "../components/GuildIcon";
import { Empty } from "../components/ui";

export default function GuildPickerPage() {
  const { data: session } = useSession();
  const navigate = useNavigate();
  const guilds = session?.guilds ?? [];

  return (
    <div className="container">
      <div className="page-header">
        <div className="page-header__title">Your servers</div>
        <div className="page-header__desc">
          Servers where you have Manage Server and the bot is present.
        </div>
      </div>

      {guilds.length === 0 ? (
        <Empty>
          No manageable servers found. Make sure the bot is in your server and that you have the
          <strong> Manage Server</strong> permission there.
        </Empty>
      ) : (
        <div className="guild-grid">
          {guilds.map((g) => (
            <div key={g.id} className="guild-card" onClick={() => navigate(`/guilds/${g.id}`)}>
              <GuildIcon guild={g} />
              <div style={{ fontWeight: 700, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
                {g.name}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
