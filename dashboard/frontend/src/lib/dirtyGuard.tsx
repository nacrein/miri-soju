// Unsaved-edit navigation guard. A panel's SaveBar dirty state lives inside the
// panel, but the things that navigate away (the left module nav, the Miri brand
// link, a tab close/refresh) live outside it. So the open panel publishes its
// dirty flag into this context; the navigation triggers read it back.
//
// Two guards, because the app uses <BrowserRouter> (not a data router, so
// react-router's useBlocker is unavailable):
//   1. a window 'beforeunload' listener, covers tab close, refresh, and
//      navigation to an external URL;
//   2. confirmDiscard(), an explicit window.confirm() the in-app navigators
//      (module nav, brand link) call before routing away.
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

const DISCARD_PROMPT = "You have unsaved changes that will be lost. Leave anyway?";

interface DirtyGuard {
  /** Mark the open panel dirty/clean. Called from useDirtyGuard. */
  setDirty: (dirty: boolean) => void;
  /** True while the open panel has unsaved edits. */
  dirty: boolean;
  /** Returns true if it's safe to navigate (clean, or the user confirmed). */
  confirmDiscard: () => boolean;
}

const DirtyGuardContext = createContext<DirtyGuard | null>(null);

export function DirtyGuardProvider({ children }: { children: ReactNode }) {
  const [dirty, setDirty] = useState(false);

  // Native guard for tab close / refresh / external navigation.
  useEffect(() => {
    if (!dirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Legacy browsers require returnValue to be set to show the prompt.
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty]);

  const confirmDiscard = useCallback(
    () => !dirty || window.confirm(DISCARD_PROMPT),
    [dirty],
  );

  return (
    <DirtyGuardContext.Provider value={{ setDirty, dirty, confirmDiscard }}>
      {children}
    </DirtyGuardContext.Provider>
  );
}

/** Read the guard. Returns a no-op guard if no provider is mounted (e.g. tests),
 *  so panels and the nav never crash outside the provider. */
export function useDirtyGuardContext(): DirtyGuard {
  return (
    useContext(DirtyGuardContext) ?? {
      setDirty: () => {},
      dirty: false,
      confirmDiscard: () => true,
    }
  );
}

/** Panels call this with their form's dirty flag to publish it to the guard.
 *  Clears the flag on unmount so a discarded/closed panel can't keep the app
 *  pinned as dirty. */
export function useDirtyGuard(dirty: boolean) {
  const { setDirty } = useDirtyGuardContext();
  useEffect(() => {
    setDirty(dirty);
    return () => setDirty(false);
  }, [dirty, setDirty]);
}
