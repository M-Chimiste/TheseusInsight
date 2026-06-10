import { useCallback, useState } from 'react';

export type DialogState<T> = {
  open: boolean;
  /** Payload the dialog was opened with (e.g. the row being edited/deleted). */
  data: T | null;
  openWith: (data: T) => void;
  openEmpty: () => void;
  close: () => void;
};

/**
 * Replaces the boolean-triplet dialog pattern
 * (`deleteDialogOpen` + `itemToDelete`, etc.) with one stateful handle
 * per dialog.
 */
export function useDialogState<T>(): DialogState<T> {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<T | null>(null);

  const openWith = useCallback((value: T) => {
    setData(value);
    setOpen(true);
  }, []);

  const openEmpty = useCallback(() => {
    setData(null);
    setOpen(true);
  }, []);

  // Keep `data` on close so exit animations don't render an empty dialog;
  // the next openWith/openEmpty resets it.
  const close = useCallback(() => setOpen(false), []);

  return { open, data, openWith, openEmpty, close };
}
