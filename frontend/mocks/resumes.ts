import type { Resume } from '../types';

// Sample metadata only. No upload, storage, or mutation behavior is mocked here.
export const mockResumes: Resume[] = [
  {
    id: 'sample-resume-1',
    name: 'Sample Resume',
    tags: ['software'],
    uploadedAt: '2026-10-16T00:00:00.000Z',
  },
];
