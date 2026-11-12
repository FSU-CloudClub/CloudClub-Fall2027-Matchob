import { resumeApi } from './resumeApi';

export interface UploadResult {
  resumeId: string;
}

export async function uploadResume(file: File): Promise<UploadResult> {
  const contentType = file.type || (file.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : '');
  const { resumeId, uploadUrl } = await resumeApi.getUploadUrl(file.name, contentType);
  try {
    // Presigned S3 requests must not include the API's local-user header.
    const response = await fetch(uploadUrl, {
      method: 'PUT', headers: { 'Content-Type': contentType }, body: file,
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
    throw new Error('File upload failed. Check that local S3 is running and try again.');
  }
  return { resumeId };
}
