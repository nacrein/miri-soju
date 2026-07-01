import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import { useSession } from "../auth/session";
import { GuildIcon } from "../components/GuildIcon";
import { Empty } from "../components/ui";
import { springSnappy, staggerContainer, staggerItem } from "../lib/motion";

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
        <motion.div className="guild-grid" variants={staggerContainer} initial="hidden" animate="visible">
          {guilds.map((g) => (
            <motion.div
              key={g.id}
              className="guild-card"
              variants={staggerItem}
              whileHover={{ y: -4 }}
              whileTap={{ scale: 0.98 }}
              transition={springSnappy}
              onClick={() => navigate(`/guilds/${g.id}`)}
            >
              <GuildIcon guild={g} />
              <div style={{ fontWeight: 700, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
                {g.name}
              </div>
            </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  );
}
