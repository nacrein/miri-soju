// Small motion helpers — scroll-reveal + count-up — that quietly no-op when the
// visitor prefers reduced motion.
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

/** Fades + rises its children into view the first time they're scrolled to. */
export function Reveal({
  children,
  className,
  delay,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reducedMotion()) {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setShown(true);
            io.disconnect();
          }
        }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={"reveal " + (shown ? "reveal--in " : "") + (className ?? "")}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/** Counts from 0 up to `target` on mount (instant under reduced motion). */
export function useCountUp(target: number, ms = 1000): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (reducedMotion()) {
      setValue(target);
      return;
    }
    let raf = 0;
    let start = 0;
    const tick = (t: number) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / ms);
      setValue(Math.round(target * easeOut(p)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return value;
}

/** True shortly after mount — flip a width/height from 0 to animate bars in. */
export function useGrow(delay = 60): boolean {
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    if (reducedMotion()) {
      setGrown(true);
      return;
    }
    const id = window.setTimeout(() => setGrown(true), delay);
    return () => window.clearTimeout(id);
  }, [delay]);
  return grown;
}
