import { useCallback, useState } from 'react';
import { resumeApi } from '../../services/resumeApi';
import type { Resume } from '../../types';

export type DeleteState =
  | { status: 'idle' }
  | { status: 'confirming'; resume: Resume }
  | { status: 'deleting'; resume: Resume }
  | { status: 'error'; resume: Resume; message: string };

export function useResumeDelete(onDeleted: (resume: Resume) => void) {
  const [state, setState] = useState<DeleteState>({ status: 'idle' });

  const request = useCallback((resume: Resume) => {
    setState({ status: 'confirming', resume });
  }, []);

   const cancel = useCallback(() => {
    setState((s) => (s.status === 'deleting' ? s : { status: 'idle' }));
  }, []);

  const confirm = useCallback(async () => {
    if (state.status !== 'confirming' && state.status !== 'error') return;
    const { resume } = state;

    setState({ status: 'deleting', resume });
    try {
      await resumeApi.deleteResume(resume.id);
      setState({ status: 'idle' });
      onDeleted(resume);
    } catch (err) {
      setState({
        status: 'error',
        resume,
        message: err instanceof Error ? err.message : 'Something went wrong. Please try again.',
      });
    }
  }, [state, onDeleted]);

  return { state, request, cancel, confirm };
}