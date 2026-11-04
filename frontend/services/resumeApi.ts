import { mockResumes } from '../mocks/resumes';
import type { Resume, UploadUrlResponse } from '../types';

export interface ResumeApi {
  getResumes(): Promise<Resume[]>;
  getUploadUrl(fileName: string, contentType: string): Promise<UploadUrlResponse>;
  renameResume(id: string, name: string): Promise<Resume>;
  updateTags(id: string, tags: string[]): Promise<Resume>;
  deleteResume(id: string): Promise<void>;
  getDownloadUrl(id: string): Promise<string>;
}

function pending(task: string): never {
  throw new Error(`${task} is a Sprint 1 team task and is not implemented yet.`);
}

const MOCK_DELETE_LATENCY_MS = 800;

const deletedMockIds = new Set<string>();

export const mockDeleteConfig = { failNextDelete: false };

function wait(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

export const resumeApi: ResumeApi = {
  async getResumes() {
    return mockResumes
      .filter((resume) => !deletedMockIds.has(resume.id))
      .map((resume) => ({ ...resume, tags: [...resume.tags] }));
  },
  async getUploadUrl(_fileName, _contentType) {
    // TODO: Sprint 1 - S3 Presigned Upload Integration.
    return pending('Presigned upload');
  },
  async renameResume(_id, _name) {
    // TODO: Sprint 1 - Resume Tags + Rename UI.
    return pending('Resume rename');
  },
  async updateTags(_id, _tags) {
    // TODO: Sprint 1 - Resume Tags + Rename UI.
    return pending('Resume tag update');
  },
  async deleteResume(id) {
    await wait(MOCK_DELETE_LATENCY_MS);

    if (mockDeleteConfig.failNextDelete) {
      mockDeleteConfig.failNextDelete = false;
      throw new Error("Couldn't delete this resume. Please try again.");
    }

    if (deletedMockIds.has(id)) {
      throw new Error('This resume no longer exists. Refresh your vault and try again.');
    }

    deletedMockIds.add(id);
  },
  async getDownloadUrl(_id) {
    return pending('Resume download');
  },
};