import { browser } from 'wxt/browser';

// Frontend-only fixture boundary. Replace this resolver with Backend's file URL API.
export async function getResumeFile(id: string, signal?: AbortSignal): Promise<Blob> {
  const local = await readLocalFile(id);
  if (local) return local;
  if (!id.startsWith('sample-resume-1')) throw new Error('This resume file is unavailable.');
  const response = await fetch(browser.runtime.getURL('/samples/sample-resume.pdf'), { signal });
  if (!response.ok) throw new Error('Could not load the resume file.');
  const file = await response.blob();
  if (!file.size) throw new Error('The resume file is empty.');
  return file;
}

function openFiles(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('matchob-preview-files', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('files');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('Local resume storage is unavailable.'));
  });
}

export async function saveLocalFile(id: string, file: File): Promise<void> {
  const db = await openFiles();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction('files', 'readwrite');
      transaction.objectStore('files').put(file, id);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(new Error('Could not save the local preview.'));
      transaction.onabort = () => reject(new Error('Could not save the local preview.'));
    });
  } finally { db.close(); }
}

async function readLocalFile(id: string): Promise<Blob | undefined> {
  const db = await openFiles();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction('files').objectStore('files').get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Could not read the local resume.'));
    });
  } finally { db.close(); }
}

export async function downloadResume(id: string, name: string): Promise<void> {
  const file = await getResumeFile(id);
  const url = URL.createObjectURL(file);
  const link = document.createElement('a');
  link.href = url;
  link.download = name.toLowerCase().endsWith('.pdf') ? name : `${name}.pdf`;
  link.click();
  // Give Chrome time to consume the object URL before releasing it.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
