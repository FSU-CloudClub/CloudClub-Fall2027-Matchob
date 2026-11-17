export interface UploadResult {
  key: string;
  contentType: string;
}

const MOCK_DELAY_MS = 1500;

// Mirrors s3_key() in backend/SAMproject/src/s3-pipeline/resume_helpers.py.
const EXTENSION_BY_CONTENT_TYPE: Record<string, string> = {
  'application/pdf': 'pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
};

// `contentType` must be the canonical MIME type from validation. The real upload
// sends it to POST /resumes/upload-url and as the Content-Type of the S3 PUT;
// the two must match or S3 rejects the signed request.
export async function uploadResume(file: File, contentType: string): Promise<UploadResult> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
  if (file.name.toLowerCase().includes('fail')) {
    throw new Error('Mock upload failure');
  }

  const extension = EXTENSION_BY_CONTENT_TYPE[contentType] ?? 'pdf';
  return { key: `mock/resumes/${crypto.randomUUID()}.${extension}`, contentType };
}