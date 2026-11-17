import { useEffect, useRef } from 'react';
import type { useResumeDelete } from './useResumeDelete';

type ResumeDeleteDialogProps = ReturnType<typeof useResumeDelete>;

const uploadDate = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

export function ResumeDeleteDialog({ state, cancel, confirm }: ResumeDeleteDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const open = state.status !== 'idle';
  const busy = state.status === 'deleting';
  const resume = state.status === 'idle' ? null : state.resume;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      cancelRef.current?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="resume-delete-dialog"
      aria-labelledby="resume-delete-title"
      aria-describedby="resume-delete-desc"
      onCancel={(e) => {
        // Esc key: route through state instead of letting the browser close it.
        e.preventDefault();
        if (!busy) cancel();
      }}
    >
      {resume && (
        <>
          <h2 id="resume-delete-title">Delete this resume?</h2>

          <p id="resume-delete-desc">
            <strong>{resume.name}</strong> (uploaded{' '}
            <time dateTime={resume.uploadedAt}>{uploadDate.format(new Date(resume.uploadedAt))}</time>)
            will be removed from your Resume Vault. This can't be undone.
          </p>

          {state.status === 'error' && (
            <p role="alert" className="resume-delete-error">
              {state.message}
            </p>
          )}

          <div className="resume-delete-actions">
            <button ref={cancelRef} type="button" onClick={cancel} disabled={busy}>
              Cancel
            </button>
            <button
              type="button"
              className="resume-delete-confirm"
              onClick={confirm}
              disabled={busy}
              aria-busy={busy}
            >
              {busy ? 'Deleting…' : state.status === 'error' ? 'Try again' : 'Delete resume'}
            </button>
          </div>
        </>
      )}
    </dialog>
  );
}