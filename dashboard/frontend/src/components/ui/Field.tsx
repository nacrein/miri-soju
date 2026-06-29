import type { ReactNode } from "react";

interface Props {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
}

/** Label + hint/error wrapper shared by every input control. */
export function Field({ label, hint, error, children }: Props) {
  return (
    <div className="field">
      {label && <label className="field__label">{label}</label>}
      {children}
      {error ? (
        <span className="field__error">{error}</span>
      ) : (
        hint && <span className="field__hint">{hint}</span>
      )}
    </div>
  );
}
