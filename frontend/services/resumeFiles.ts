import { resumeApi } from './resumeApi';

// Fetches a resume's bytes through the backend's presigned download URL.
export async function getResumeFile(id: string, signal?: AbortSignal): Promise<Blob> {
  if (!id) throw new Error('This resume file is unavailable.');
  const url = await resumeApi.getDownloadUrl(id);
  const response = await fetch(url, { signal: signal ?? AbortSignal.timeout(60000) });
  if (!response.ok) throw new Error(`Could not load the resume file (${response.status}).`);
  const file = await response.blob();
  if (!file.size) throw new Error('The resume file is empty.');
  return file;
}

export async function downloadResume(id: string, name: string): Promise<void> {
  const file = await getResumeFile(id);
  const url = URL.createObjectURL(file);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  // Give Chrome time to consume the object URL before releasing it.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
