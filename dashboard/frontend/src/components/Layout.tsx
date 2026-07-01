import type { MouseEvent, ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import { loginRedirect, useLogout, useSession } from "../auth/session";
import { useDirtyGuardContext } from "../lib/dirtyGuard";
import { avatarUrl, displayName } from "../lib/discord";
import { Button } from "./ui";

export function Layout({ children }: { children: ReactNode }) {
  const { data: session } = useSession();
  const logout = useLogout();
  const { confirmDiscard } = useDirtyGuardContext();
  const avatar = session ? avatarUrl(session.user) : null;

  // Block in-app navigation while a config form has unsaved edits.
  const guard = (e: MouseEvent) => {
    if (!confirmDiscard()) e.preventDefault();
  };

  const navClass = ({ isActive }: { isActive: boolean }) =>
    "topnav__link" + (isActive ? " topnav__link--active" : "");

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__left">
          <Link to="/" className="topbar__brand" onClick={guard}>
            <span className="dot" /> Miri
          </Link>
          <nav className="topnav">
            <NavLink to="/commands" className={navClass} onClick={guard}>
              Commands
            </NavLink>
            <NavLink to="/embed" className={navClass} onClick={guard}>
              Embed Builder
            </NavLink>
          </nav>
        </div>

        <div className="topbar__actions">
          {session ? (
            <>
              {session.is_staff && (
                <NavLink to="/staff" className={navClass} onClick={guard}>
                  Staff
                </NavLink>
              )}
              <Link to="/dashboard" className="btn btn--ghost btn--sm" onClick={guard}>
                Dashboard
              </Link>
              <div className="topbar__user">
                <div className="avatar">{avatar && <img src={avatar} alt="" />}</div>
                <span className="muted topbar__name">{displayName(session.user)}</span>
                <Button variant="ghost" size="sm" onClick={logout}>
                  Log out
                </Button>
              </div>
            </>
          ) : (
            <Button variant="primary" size="sm" onClick={loginRedirect}>
              Log in
            </Button>
          )}
        </div>
      </header>

      <div className="app-shell__body">{children}</div>

      <footer className="footer">
        <div className="footer__inner">
          <span className="topbar__brand">
            <span className="dot" /> Miri
          </span>
          <div className="footer__links">
            <Link to="/commands" onClick={guard}>Commands</Link>
            <Link to="/embed" onClick={guard}>Embed Builder</Link>
            <Link to="/dashboard" onClick={guard}>Dashboard</Link>
          </div>
          <span className="faint">Made with warmth · Miri</span>
        </div>
      </footer>
    </div>
  );
}
