import type { ReactNode } from "react";

import { Field } from "./Field";

/** Clamp n into [min, max]; either bound may be undefined (treated as open). */
function clamp(n: number, min?: number, max?: number): number {
  if (min !== undefined && n < min) return min;
  if (max !== undefined && n > max) return max;
  return n;
}

// ── text ────────────────────────────────────────────────────────────────────
interface TextFieldProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength?: number;
  mono?: boolean;
  disabled?: boolean;
}

export function TextField({ label, hint, error, value, onChange, placeholder, maxLength, mono, disabled }: TextFieldProps) {
  return (
    <Field label={label} hint={hint} error={error}>
      <input
        className={"input" + (mono ? " mono" : "")}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}

// ── number ──────────────────────────────────────────────────────────────────
interface NumberFieldProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
}

export function NumberField({ label, hint, error, value, onChange, min, max, step, disabled }: NumberFieldProps) {
  return (
    <Field label={label} hint={hint} error={error}>
      <input
        type="number"
        className="input"
        value={Number.isFinite(value) ? value : ""}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        onChange={(e) => {
          // Never emit NaN: an empty/invalid field would serialize to null and the
          // backend's required int fields would 422. Coalesce to the min (or 0).
          const raw = e.target.value;
          if (raw === "") return onChange(min ?? 0);
          const n = Number(raw);
          // Clamp to [min, max] so out-of-range values can't round-trip and surface
          // as an opaque backend 422, the backend bounds mirror these min/max props.
          onChange(clamp(Number.isFinite(n) ? n : (min ?? 0), min, max));
        }}
      />
    </Field>
  );
}

// ── textarea ────────────────────────────────────────────────────────────────
interface TextAreaProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength?: number;
  rows?: number;
  disabled?: boolean;
}

export function TextArea({ label, hint, error, value, onChange, placeholder, maxLength, rows, disabled }: TextAreaProps) {
  return (
    <Field label={label} hint={hint} error={error}>
      <textarea
        className="textarea"
        value={value}
        rows={rows}
        placeholder={placeholder}
        maxLength={maxLength}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}

// ── select ──────────────────────────────────────────────────────────────────
export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  value: string | null;
  onChange: (value: string | null) => void;
  options: SelectOption[];
  /** Shown as the first, empty option; selecting it yields null. Omit to force a pick. */
  placeholder?: string;
  disabled?: boolean;
}

export function Select({ label, hint, error, value, onChange, options, placeholder, disabled }: SelectProps) {
  return (
    <Field label={label} hint={hint} error={error}>
      <select
        className="select"
        value={value ?? ""}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}
