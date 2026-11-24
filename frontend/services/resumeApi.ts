import type { Resume, UploadUrlResponse } from '../types';

export interface ResumeApi {
  getResumes(): Promise<Resume[]>;
  getUploadUrl(fileName: string, contentType: string): Promise<UploadUrlResponse>;
  renameResume(id: string, name: string): Promise<Resume>;
  updateTags(id: string, tags: string[]): Promise<Resume>;
  deleteResume(id: string): Promise<void>;
  getDownloadUrl(id: string): Promise<string>;
}

// Local integration only: never send the test identity to a remote API.
const baseUrl = (import.meta.env.WXT_API_BASE_URL || 'http://localhost:3001').replace(/\/$/, '');
const localUser = import.meta.env.WXT_LOCAL_USER || '12345';

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const endpoint = new URL(baseUrl);
  if (!['localhost', '127.0.0.1'].includes(endpoint.hostname)) {
    throw new Error('This API client is configured for local testing only. Use a localhost API URL.');
  }
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method,
      headers: {
        'X-Local-User': localUser,
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });
  } catch {
    throw new Error('Cannot reach the local backend. Start backend/SAMproject/dev.py and try again.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.error || data?.message || `Request failed (${response.status})`);
  }
  if (data === null) throw new Error('The backend returned an invalid response.');
  return data as T;
}

const resumePath = (id: string) => `/resumes/${encodeURIComponent(id)}`;

export const resumeApi: ResumeApi = {
  getResumes: () => request<Resume[]>('/resumes'),
  getUploadUrl: (fileName, contentType) => request<UploadUrlResponse>('/resumes/upload-url', 'POST', { fileName, contentType }),
  renameResume: (id, name) => request<Resume>(resumePath(id), 'PATCH', { name }),
  updateTags: (id, tags) => request<Resume>(resumePath(id), 'PATCH', { tags }),
  async deleteResume(id) {
    await request(resumePath(id), 'DELETE');
  },
  async getDownloadUrl(id) {
    const result = await request<{ downloadUrl: string; expiresIn: number }>(`${resumePath(id)}/download-url`);
    return result.downloadUrl;
  },
};
