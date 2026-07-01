import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { loginRedirect, useLogout, useSession } from "../auth/session";
import { easeSmooth } from "../lib/motion";
import { useDirtyGuardContext } from "../lib/dirtyGuard";
import { avatarUrl, displayName } from "../lib/discord";
import { Button } from "./ui";

export function Layout({ children }: { children: ReactNode }) {
  const { data: session, isLoading } = useSession();
  const logout = useLogout();
  const { confirmDiscard } = useDirtyGuardContext();
  const avatar = session ? avatarUrl(session.user) : null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <motion.div
          className="topbar__inner"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: easeSmooth }}
        >
          <Link
            to="/"
            className="topbar__brand"
            onClick={(e) => {
              if (!confirmDiscard()) e.preventDefault();
            }}
          >
            <span className="dot" /> Miri
          </Link>
          {session ? (
            <div className="topbar__user">
              <div className="avatar">{avatar && <img src={avatar} alt="" />}</div>
              <span className="muted">{displayName(session.user)}</span>
              <Button variant="ghost" size="sm" onClick={logout}>
                Log out
              </Button>
            </div>
          ) : (
            !isLoading && (
              <Button variant="primary" size="sm" onClick={loginRedirect}>
                Log in
              </Button>
            )
          )}
        </motion.div>
      </header>
      {children}
    </div>
  );
}
