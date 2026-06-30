import { Button } from "./Button";

interface Props {
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
  onReset: () => void;
  error?: string | null;
  justSaved?: boolean;
  /** Client-side validation message; when set, Save is blocked and this is shown. */
  invalid?: string | null;
}

/** Sticky footer that appears under a form: shows dirty/saved/error state + actions. */
export function SaveBar({ dirty, saving, onSave, onReset, error, justSaved, invalid }: Props) {
  let status = "";
  if (error) status = error;
  else if (invalid && dirty) status = invalid;
  else if (saving) status = "Saving…";
  else if (dirty) status = "You have unsaved changes";
  else if (justSaved) status = "All changes saved";

  const showError = !!error || (!!invalid && dirty);

  return (
    <div className="savebar">
      <span className="savebar__status" style={showError ? { color: "var(--danger)" } : undefined}>
        {status}
      </span>
      <div className="row">
        <Button variant="ghost" size="sm" onClick={onReset} disabled={!dirty || saving}>
          Reset
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={onSave}
          disabled={!dirty || saving || (!!invalid && dirty)}
        >
          Save changes
        </Button>
      </div>
    </div>
  );
}
