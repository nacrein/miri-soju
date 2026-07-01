import { motion } from "framer-motion";

import { loginRedirect } from "../auth/session";
import { Alert } from "../components/ui";
import { easeSmooth, springSnappy, staggerContainer, staggerItem } from "../lib/motion";
import { MODULES } from "./modules/registry";

// A curated taste of what the bot does — headline features shown as pillars,
// with the full module list (from the real registry) below to convey breadth.
const PILLARS = [
  {
    icon: "🛡️",
    title: "AutoMod & Moderation",
    desc: "Filter spam, invites, links and slurs, then escalate to timeouts, kicks and bans — automatically.",
  },
  {
    icon: "📈",
    title: "Leveling & Rewards",
    desc: "Reward your most active members with XP, automatic role rewards and per-channel multipliers.",
  },
  {
    icon: "🎵",
    title: "Music & Voice",
    desc: "Crisp music playback plus on-demand VoiceMaster rooms your members create and control themselves.",
  },
];

/** Official Discord mark, inherits the button's text color via currentColor. */
function DiscordMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.317 4.3698a19.7913 19.7913 0 0 0-4.8851-1.5152.0741.0741 0 0 0-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 0 0-.0785-.037 19.7363 19.7363 0 0 0-4.8852 1.515.0699.0699 0 0 0-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 0 0 .0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 0 0 .0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 0 0-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 0 1-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 0 1 .0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 0 1 .0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 0 1-.0066.1276 12.2986 12.2986 0 0 1-1.873.8914.0766.0766 0 0 0-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 0 0 .0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 0 0 .0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 0 0-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189z" />
    </svg>
  );
}

export default function LoginPage() {
  const error = new URLSearchParams(window.location.search).get("error");

  return (
    <div className="landing">
      <div className="landing__orb landing__orb--1" aria-hidden="true" />
      <div className="landing__orb landing__orb--2" aria-hidden="true" />

      {/* ── hero ── */}
      <motion.section className="landing__hero" variants={staggerContainer} initial="hidden" animate="visible">
        <motion.div className="landing__eyebrow" variants={staggerItem}>
          <span className="landing__eyebrow-dot" /> The all-in-one Discord bot
        </motion.div>
        <motion.h1 className="landing__title" variants={staggerItem}>
          Everything your server needs,
          <br />
          <span className="landing__title-accent">in one bot.</span>
        </motion.h1>
        <motion.p className="landing__sub" variants={staggerItem}>
          Moderation, automod, leveling, music, starboards and more — all configured from a fast,
          modern dashboard. Log in with Discord and set your server up in minutes.
        </motion.p>

        {error && (
          <motion.div className="landing__error" variants={staggerItem}>
            <Alert tone="danger">
              {error === "discord"
                ? "Couldn’t reach Discord. Please try again."
                : "Login failed or was cancelled."}
            </Alert>
          </motion.div>
        )}

        <motion.div className="landing__cta" variants={staggerItem}>
          <button type="button" className="btn btn--primary landing__cta-btn" onClick={loginRedirect}>
            <DiscordMark /> Log in with Discord
          </button>
          <a className="btn btn--ghost landing__cta-btn" href="#features">
            Explore features
          </a>
        </motion.div>
        <motion.div className="landing__trust" variants={staggerItem}>
          Free to add · {MODULES.length} modules · Configure in minutes
        </motion.div>
      </motion.section>

      {/* ── feature pillars ── */}
      <section className="landing__section" id="features">
        <div className="landing__section-head">
          <h2 className="landing__section-title">Built for every corner of your server</h2>
          <p className="landing__section-desc">
            One bot instead of five. Here’s a taste of what Miri handles out of the box.
          </p>
        </div>
        <motion.div
          className="feature-grid"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-80px" }}
        >
          {PILLARS.map((f) => (
            <motion.div
              key={f.title}
              className="feature-card"
              variants={staggerItem}
              whileHover={{ y: -6 }}
              transition={springSnappy}
            >
              <div className="feature-icon">{f.icon}</div>
              <div className="feature-card__title">{f.title}</div>
              <p className="feature-card__desc">{f.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* ── every module ── */}
      <section className="landing__section">
        <div className="landing__section-head">
          <h2 className="landing__section-title">…and {MODULES.length} modules in total</h2>
          <p className="landing__section-desc">
            Switch on only what you need — everything shares one clean dashboard.
          </p>
        </div>
        <motion.div
          className="module-chips"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-60px" }}
        >
          {MODULES.map((m) => (
            <motion.div
              key={m.key}
              className="module-chip"
              variants={staggerItem}
              whileHover={{ y: -3 }}
              transition={springSnappy}
            >
              <span className="module-chip__icon">{m.icon}</span> {m.label}
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* ── final CTA ── */}
      <motion.section
        className="landing__final"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5, ease: easeSmooth }}
      >
        <h2 className="landing__final-title">Ready to run your server on autopilot?</h2>
        <p className="landing__final-desc">
          Log in with Discord — no setup fee, no clutter, just the modules you switch on.
        </p>
        <button type="button" className="btn btn--primary landing__cta-btn" onClick={loginRedirect}>
          <DiscordMark /> Log in with Discord
        </button>
      </motion.section>

      <footer className="landing__footer">
        <span className="landing__brand">
          <span className="landing__brand-dot" /> Miri
        </span>
        <span className="faint">© Miri · Manage your Discord server, beautifully.</span>
      </footer>
    </div>
  );
}
