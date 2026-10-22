import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { Button } from '../../components/Button';
import { uploadResume, type UploadResult } from '../../services/uploadResume';

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB placeholder: confirm with Backend/AWS
const MAX_RESUME_MB = MAX_FILE_SIZE / (1024 * 1024);

type UploadState = | { status: 'idle' }| { status: 'invalid'; message: string }| { status: 'uploading'; file: File }| { status: 'success'; file: File }| { status: 'failure'; file: File; message: string };

type ValidationResult = { valid: true } | { valid: false; message: string };

function validateFile(file: File): ValidationResult {
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

  if (!isPdf) {
    return { valid: false, message: 'Invalid file type. Please select a PDF file.' };
  }
  if (file.size === 0) {
    return { valid: false, message: 'File is empty. Please select a non-empty file.' };
  }
  if (file.size > MAX_FILE_SIZE) {
    return { valid: false, message: `File size exceeds ${MAX_RESUME_MB} MB limit.` };
  }
  return { valid: true };
}

interface ResumeUploadProps {
  onUploadComplete?: (result: UploadResult, file: File) => void;
}

export function ResumeUpload({ onUploadComplete }: ResumeUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);
  const [state, setUploadState] = useState<UploadState>({ status: 'idle' });
  const [isDragging, setIsDragging] = useState(false);

  const isUploading = state.status === 'uploading';

  function openPicker() {
    if (!isUploading) fileInputRef.current?.click();
  }

  async function startUpload(file: File) {
    setUploadState({ status: 'uploading', file });
    try {
      const result = await uploadResume(file);
      setUploadState({ status: 'success', file });
      onUploadComplete?.(result, file);
    } catch (error) {
      console.error('Upload failed:', error);
      setUploadState({ status: 'failure', file, message: 'Upload failed. Please try again.' });
    }
  }

  function handleFile(file: File) {
    const result = validateFile(file);
    if (!result.valid) {
      setUploadState({ status: 'invalid', message: result.message });
      return;
    }
    void startUpload(file);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    handleFile(file);
  }

  useEffect(() => {
    function hasFiles(event: DragEvent) {
      return event.dataTransfer?.types.includes('Files') ?? false;
    }

    function onDragEnter(event: DragEvent) {
      if (!hasFiles(event)) return;
      event.preventDefault();
      if (isUploading) return;
      dragDepth.current += 1;
      setIsDragging(true);
    }

    function onDragOver(event: DragEvent) {
      if (!hasFiles(event)) return;
      event.preventDefault(); 
      if (event.dataTransfer) event.dataTransfer.dropEffect = isUploading ? 'none' : 'copy';
    }

    function onDragLeave(event: DragEvent) {
      if (!hasFiles(event)) return;
      dragDepth.current = Math.max(0, dragDepth.current - 1);
      if (dragDepth.current === 0) setIsDragging(false);
    }

    function onDrop(event: DragEvent) {
      if (!hasFiles(event)) return;
      event.preventDefault();
      dragDepth.current = 0;
      setIsDragging(false);
      if (isUploading) return;

      const files = event.dataTransfer?.files;
      const file = files?.[0];
      if (!files || !file) return;
      if (files.length > 1) {
        setUploadState({ status: 'invalid', message: 'Please drop only one file.' });
        return;
      }
      handleFile(file);
    }

    window.addEventListener('dragenter', onDragEnter);
    window.addEventListener('dragover', onDragOver);
    window.addEventListener('dragleave', onDragLeave);
    window.addEventListener('drop', onDrop);

    return () => {
      window.removeEventListener('dragenter', onDragEnter);
      window.removeEventListener('dragover', onDragOver);
      window.removeEventListener('dragleave', onDragLeave);
      window.removeEventListener('drop', onDrop);
    };
  });

  const dropzoneClass = [
    'resume-upload__dropzone',
    isDragging && 'resume-upload__dropzone--dragging',
    state.status === 'invalid' && 'resume-upload__dropzone--error',
    isUploading && 'resume-upload__dropzone--busy',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="resume-upload">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,application/pdf"
        hidden
      />

      <Button onClick={openPicker} disabled={isUploading}>
        Upload resume
      </Button>

      <div className={dropzoneClass} aria-busy={isUploading}>
        {state.status === 'uploading' ? (
          <div className="resume-upload__uploading" role="status" aria-live="polite">
            <span className="resume-upload__spinner" aria-hidden="true" />
            <p className="resume-upload__title">Uploading {state.file.name}…</p>
          </div>
        ) : (
          <>
            <p className="resume-upload__title">
              {isDragging
                ? 'Drop to upload your resume'
                : 'Drag and drop your resume anywhere here, or use the button above.'}
            </p>
            <p className="resume-upload__hint">PDF only, up to {MAX_RESUME_MB} MB</p>
          </>
        )}
      </div>

      {state.status === 'invalid' && (
        <p className="resume-upload__error" role="alert">
          {state.message}
        </p>
      )}

      {state.status === 'success' && (
        <p className="resume-upload__success" role="status">
          Added {state.file.name} to this preview. It is not saved yet.
        </p>
      )}

      {state.status === 'failure' && (
        <div className="resume-upload__error" role="alert">
          <p>{state.message}</p>
          <Button variant="secondary" onClick={() => void startUpload(state.file)}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}
