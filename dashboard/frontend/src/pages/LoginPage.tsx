import { Link } from "react-router-dom";

import { loginRedirect } from "../auth/session";
import { Alert, Button } from "../components/ui";

export default function LoginPage() {
  const error = new URLSearchParams(window.location.search).get("error");

  return (
    <div className="login">
      <div className="card login__card">
        <div className="login__logo">
          <span className="dot" style={{ width: 18, height: 18 }} />
        </div>
        <h1 className="page-header__title">Log in to Miri</h1>
        <p className="muted" style={{ marginTop: 8, marginBottom: 24 }}>
          Sign in with Discord to manage the servers you administrate — leveling, automod, logging,
          moderation and more.
        </p>
        {error && (
          <div style={{ marginBottom: 16 }}>
            <Alert tone="danger">
              {error === "discord"
                ? "Couldn’t reach Discord. Please try again."
                : "Login failed or was cancelled."}
            </Alert>
          </div>
        )}
        <Button variant="primary" block onClick={loginRedirect}>
          Log in with Discord
        </Button>
        <Link to="/" className="muted" style={{ display: "inline-block", marginTop: 16, fontSize: "var(--text-sm)" }}>
          ← Back to home
        </Link>
      </div>
    </div>
  );
}
