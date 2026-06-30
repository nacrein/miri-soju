import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useLogout, useSession } from "../auth/session";
import { useDirtyGuardContext } from "../lib/dirtyGuard";
import { avatarUrl, displayName } from "../lib/discord";
import { Button } from "./ui";

export function Layout({ children }: { children: ReactNode }) {
  const { data: session } = useSession();
  const logout = useLogout();
  const { confirmDiscard } = useDirtyGuardContext();
  const avatar = session ? avatarUrl(session.user) : null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link
          to="/"
          className="topbar__brand"
          onClick={(e) => {
            if (!confirmDiscard()) e.preventDefault();
          }}
        >
          <span className="dot" /> Miri
        </Link>
        {session && (
          <div className="topbar__user">
            <div className="avatar">{avatar && <img src={avatar} alt="" />}</div>
            <span className="muted">{displayName(session.user)}</span>
            <Button variant="ghost" size="sm" onClick={logout}>
              Log out
            </Button>
          </div>
        )}
      </header>
      {children}
    </div>
  );
}
