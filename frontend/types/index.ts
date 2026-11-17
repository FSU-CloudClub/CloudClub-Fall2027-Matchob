export type Resume = {
  id: string;
  name: string;
  tags: string[];
  // MIME type set by the backend from the upload (PDF or DOCX). Optional until
  // getResumes() returns real data; missing is treated as PDF.
  contentType?: string;
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