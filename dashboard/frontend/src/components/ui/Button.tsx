import type { ButtonHTMLAttributes } from "react";

type Variant = "default" | "primary" | "ghost" | "danger";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
  block?: boolean;
}

export function Button({ variant = "default", size = "md", block, className = "", type = "button", ...rest }: Props) {
  const classes = ["btn"];
  if (variant !== "default") classes.push(`btn--${variant}`);
  if (size === "sm") classes.push("btn--sm");
  if (block) classes.push("btn--block");
  if (className) classes.push(className);
  return <button type={type} className={classes.join(" ")} {...rest} />;
}
