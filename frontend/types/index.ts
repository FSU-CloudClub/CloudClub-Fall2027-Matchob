export type Resume = {
  id: string;
  name: string;
  tags: string[];
  uploadedAt: string;
};

export type UploadUrlResponse = {
  resumeId: string;
  uploadUrl: string;
};

export type JobDescription = {
  title: string;
  company?: string;
  text: string;
};

export type Recommendation = {
  id: string;
  suggestion: string;
  reason: string;
};
