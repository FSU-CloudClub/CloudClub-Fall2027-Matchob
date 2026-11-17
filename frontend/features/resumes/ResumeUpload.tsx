import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { Button } from '../../components/Button';
import { uploadResume, type UploadResult } from '../../services/uploadResume';
import {
  RESUME_ACCEPT,
  RESUME_FILE_TYPES,
  RESUME_TYPES_LABEL,
  getResumeFileKind,
  isLegacyWordFile,
} from './resumeFileTypes';
import './ResumeUpload.css';

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB placeholder: confirm with Backend/AWS
const MAX_RESUME_MB = MAX_FILE_SIZE / (1024 * 1024);

type UploadState =
  | { status: 'idle' }
  | { status: 'invalid'; message: string }
  | { status: 'uploading'; file: File; contentType: string }
  | { status: 'success'; file: File }
  | { status: 'failure'; file: File; contentType: string; message: string };

type ValidationResult =
  | { valid: true; contentType: string }
  | { valid: false; message: string };

function validateFile(file: File): ValidationResult {
  const kind = getResumeFileKind(file);

  if (!kind) {
    if (isLegacyWordFile(file)) {
      return {
        valid: false,
        message: 'Older Word files (.doc) are not supported. Save it as .docx or PDF and try again.',
      };
    }
    return { valid: false, message: `Invalid file type. Please select a ${RESUME_TYPES_LABEL} file.` };
  }
  if (file.size === 0) {
    return { valid: false, message: 'File is empty. Please select a non-empty file.' };
  }
  if (file.size > MAX_FILE_SIZE) {
    return { valid: false, message: `File size exceeds ${MAX_RESUME_MB} MB limit.` };
  }
  // Send the canonical MIME type, not file.type, which can be empty or vary by OS.
  return { valid: true, contentType: RESUME_FILE_TYPES[kind].mimeType };
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

  async function startUpload(file: File, contentType: string) {
    setUploadState({ status: 'uploading', file, contentType });
    try {
      const result = await uploadResume(file, contentType);
      setUploadState({ status: 'success', file });
      onUploadComplete?.(result, file);
    } catch (error) {
      console.error('Upload failed:', error);
      setUploadState({ status: 'failure', file, contentType, message: 'Upload failed. Please try again.' });
    }
  }

  function handleFile(file: File) {
    const result = validateFile(file);
    if (!result.valid) {
      setUploadState({ status: 'invalid', message: result.message });
      return;
    }
    void startUpload(file, result.contentType);
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
        accept={RESUME_ACCEPT}
        hidden
      />

      <button
        type="button"
        className={dropzoneClass}
        onClick={openPicker}
        disabled={isUploading}
        aria-busy={isUploading}
      >
        {state.status === 'uploading' ? (
          <span className="resume-upload__uploading" role="status" aria-live="polite">
            <span className="resume-upload__spinner" aria-hidden="true" />
            Uploading {state.file.name}…
          </span>
        ) : (
          <>
            <span className="resume-upload__title">
              {isDragging ? 'Drop to upload' : `Drag a ${RESUME_TYPES_LABEL} here, or`}
            </span>
            <span className="resume-upload__action">Choose a file to upload</span>
            <span className="resume-upload__hint">
              {RESUME_TYPES_LABEL}, up to {MAX_RESUME_MB} MB
            </span>
          </>
        )}
      </button>

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
          <Button variant="secondary" onClick={() => void startUpload(state.file, state.contentType)}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}