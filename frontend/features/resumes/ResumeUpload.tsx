import { useRef, useState, type ChangeEvent } from 'react';
import { Button } from '../../components/Button';

type UploadState = |{status: 'idle'}| {status: 'invalid'; message:String} | {status: 'uploading'; file:File} | {status: 'success'; file: File} | {status: 'failure'; file:File; message:string};

type ValidationResult = { valid: true } | { valid: false; message: string };

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

function validateFile(file: File): ValidationResult {

  const isPdf=file.type=='application/pdf' || file.name.toLocaleLowerCase().endsWith('.pdf');

  if (!isPdf) {
    return { valid: false, message: 'Invalid file type. Please select a PDF file.' };
  }
  if (file.size > MAX_FILE_SIZE) {
    return { valid: false, message: 'File size exceeds 5MB limit.' };
  }
  if (file.size==0) {
    return { valid: false, message: 'File is empty. Please select a non-empty file.' };
  }
  return { valid: true };
}

export function ResumeUpload() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [state, setUploadState] = useState<UploadState>({status: 'idle'});

  function openPicker() {
    fileInputRef.current?.click();
  }
  function handleUpload(file: File) {
    const result = validateFile(file);
    if (!result.valid) {
      setUploadState({status: 'invalid', message: result.message});
      return;
    }
    setUploadState({status: 'uploading', file});
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow choosing the same file again
    if (!file) return;
    handleUpload(file);
  }

  return (
    <div>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,application/pdf"
        hidden
      />
      <Button onClick={openPicker}>Upload resume</Button>
      {state.status === 'idle' && <p>No file selected.</p>}
      {state.status === 'invalid' && <p>{state.message}</p>}
      {state.status === 'uploading' && <p>Uploading...</p>}
      {state.status === 'success' && <p>Upload successful!</p>}
      {state.status === 'failure' && <p>{state.message}</p>}
      
    </div>
  );
}