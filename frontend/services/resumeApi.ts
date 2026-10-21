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

// Mock read boundary for independent UI work. Mutations stay as explicit stubs.
export const resumeApi: ResumeApi = {
  async getResumes() {
    return mockResumes.map((resume) => ({ ...resume, tags: [...resume.tags] }));
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
  async deleteResume(_id) {
    // TODO: Sprint 1 - Resume Delete Flow.
    return pending('Resume deletion');
  },
  async getDownloadUrl(_id) {
    // TODO: Sprint 1 - Resume Preview + Download UI.
    return pending('Resume download');
  },
};
