// Shared motion vocabulary, one place for the dashboard's easing, springs, and
// entrance choreography, so every surface moves with the same intent. Framer
// Motion is the only animation dependency; all *visual* values still come from
// tokens.css. Keep this restrained: soft, decelerating, no wobble (the
// evict/rival house style), and always deferential to prefers-reduced-motion
// (enforced globally via <MotionConfig reducedMotion="user"> in App).
import type { Transition, Variants } from "framer-motion";

// A soft, decelerating curve (easeOutQuint-ish), the default for entrances.
export const easeSmooth: [number, number, number, number] = [0.22, 1, 0.36, 1];

// Springs: "soft" for large surfaces (panels, the nav indicator, the save bar),
// "snappy" for small controls (the switch knob, card taps). Both settle fast.
export const springSoft: Transition = { type: "spring", stiffness: 320, damping: 34, mass: 0.9 };
export const springSnappy: Transition = { type: "spring", stiffness: 520, damping: 34, mass: 0.7 };

// Reveal a set of children in a quick cascade. Pair a `staggerContainer` parent
// with `staggerItem` children (e.g. the guild grid).
export const staggerContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.055, delayChildren: 0.03 } },
};
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: easeSmooth } },
};

// Route/page swap: the outgoing page lifts away as the next fades up beneath it.
export const pageTransition: Variants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.32, ease: easeSmooth } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.2, ease: easeSmooth } },
};
