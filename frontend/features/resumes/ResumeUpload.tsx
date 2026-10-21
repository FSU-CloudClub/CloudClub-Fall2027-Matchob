import { useRef, useState, type ChangeEvent } from 'react';
import { Button } from '../../components/Button';

type UploadState = |{status: 'idle'}| {status: 'invalid'; message:String} | {status: 'uploading'; file:File} | {status: 'success'; file: File} | {status: 'failure'; file:File; message:string};

export function ResumeUpload() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [state, setUploadState] = useState<UploadState>({status: 'idle'});

  function openPicker() {
    fileInputRef.current?.click();
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow choosing the same file again
    if (!file) return;
    console.log('Selected file:', file.name, file.type, file.size);
    if (file.type !== 'application/pdf') {
      setUploadState({status: 'invalid', message: 'Invalid file type. Please select a PDF file.'});
      return;
    }
    if (file.name.toLocaleLowerCase().endsWith('.pdf') === false) {
      setUploadState({status: 'invalid', message: 'Invalid file type. Please select a PDF file.'});
      return;
    }
    setUploadState({status: 'uploading', file});
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