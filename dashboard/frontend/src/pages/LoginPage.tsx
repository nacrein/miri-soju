import { loginRedirect } from "../auth/session";
import { Alert, Button } from "../components/ui";

export default function LoginPage() {
  const error = new URLSearchParams(window.location.search).get("error");

  return (
    <div className="login">
      <div className="card login__card">
        <div className="login__logo">🤖</div>
        <h1 className="page-header__title">Bot Dashboard</h1>
        <p className="muted" style={{ marginTop: 8, marginBottom: 24 }}>
          Configure your server’s bot settings from the browser. Log in with Discord to manage the
          servers you administrate.
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
      </div>
    </div>
  );
}
