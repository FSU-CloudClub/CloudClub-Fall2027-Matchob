import { resumeApi } from './resumeApi';

export interface UploadResult {
  resumeId: string;
  contentType: string;
}

// `contentType` must be the canonical MIME type from validation. It is sent to
// POST /resumes/upload-url and as the Content-Type of the S3 PUT; the two must
// match or S3 rejects the signed request.
export async function uploadResume(file: File, contentType: string): Promise<UploadResult> {
  const { resumeId, uploadUrl } = await resumeApi.getUploadUrl(file.name, contentType);
  try {
    // Presigned S3 requests must not include the API's local-user header.
    const response = await fetch(uploadUrl, {
      method: 'PUT',
      headers: { 'Content-Type': contentType },
      body: file,
      signal: AbortSignal.timeout(60000),
    });
    if (!response.ok) throw new Error(`File upload failed (${response.status}).`);
  } catch {
    // The backend creates metadata before uploading. Remove it on failure.
    try {
      await resumeApi.deleteResume(resumeId);
    } catch {
      throw new Error('Upload failed and cleanup failed. Refresh the Vault and delete the incomplete resume before retrying.');
    }
    throw new Error('File upload failed. Check that S3 is reachable and try again.');
  }
  return { resumeId, contentType };
}
