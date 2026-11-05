export interface UploadResult {
  key: string;
}

const MOCK_DELAY_MS = 1500;

export async function uploadResume(file: File): Promise<UploadResult> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
  if (file.name.toLowerCase().includes('fail')) {
    throw new Error('Mock upload failure');
  }

  return { key: `mock/resumes/${crypto.randomUUID()}.pdf` };
}