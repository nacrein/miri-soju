import type { ReactNode } from "react";
import { motion } from "framer-motion";

import { easeSmooth } from "../../lib/motion";

interface Props {
  title?: ReactNode;
  desc?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}

export function Card({ title, desc, footer, children }: Props) {
  return (
    <motion.section
      className="card"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: easeSmooth }}
    >
      {(title || desc) && (
        <header className="card__header">
          {title && <div className="card__title">{title}</div>}
          {desc && <div className="card__desc">{desc}</div>}
        </header>
      )}
      <div className="card__body">{children}</div>
      {footer && <footer className="card__footer">{footer}</footer>}
    </motion.section>
  );
}
