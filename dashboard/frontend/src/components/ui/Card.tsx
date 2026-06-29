import type { ReactNode } from "react";

interface Props {
  title?: ReactNode;
  desc?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}

export function Card({ title, desc, footer, children }: Props) {
  return (
    <section className="card">
      {(title || desc) && (
        <header className="card__header">
          {title && <div className="card__title">{title}</div>}
          {desc && <div className="card__desc">{desc}</div>}
        </header>
      )}
      <div className="card__body">{children}</div>
      {footer && <footer className="card__footer">{footer}</footer>}
    </section>
  );
}
