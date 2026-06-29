import { Button } from "./Button";

interface Props {
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
  onReset: () => void;
  error?: string | null;
  justSaved?: boolean;
}

/** Sticky footer that appears under a form: shows dirty/saved/error state + actions. */
export function SaveBar({ dirty, saving, onSave, onReset, error, justSaved }: Props) {
  let status = "";
  if (error) status = error;
  else if (saving) status = "Saving…";
  else if (dirty) status = "You have unsaved changes";
  else if (justSaved) status = "All changes saved";

  return (
    <div className="savebar">
      <span className="savebar__status" style={error ? { color: "var(--danger)" } : undefined}>
        {status}
      </span>
      <div className="row">
        <Button variant="ghost" size="sm" onClick={onReset} disabled={!dirty || saving}>
          Reset
        </Button>
        <Button variant="primary" size="sm" onClick={onSave} disabled={!dirty || saving}>
          Save changes
        </Button>
      </div>
    </div>
  );
}
