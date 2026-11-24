export const RESUME_FILE_TYPES = {
  pdf: {
    extension: '.pdf',
    mimeType: 'application/pdf',
    label: 'PDF',
  },
  docx: {
    extension: '.docx',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    label: 'DOCX',
  },
} as const;

export type ResumeFileKind = keyof typeof RESUME_FILE_TYPES;

const KINDS = Object.keys(RESUME_FILE_TYPES) as ResumeFileKind[];

export const RESUME_ACCEPT = KINDS.flatMap((kind) => [
  RESUME_FILE_TYPES[kind].extension,
  RESUME_FILE_TYPES[kind].mimeType,
]).join(',');

export const RESUME_TYPES_LABEL = KINDS.map((kind) => RESUME_FILE_TYPES[kind].label).join(' or ');

export function getResumeFileKind(file: Pick<File, 'name' | 'type'>): ResumeFileKind | null {
  const name = file.name.toLowerCase();
  const byExtension = KINDS.find((kind) => name.endsWith(RESUME_FILE_TYPES[kind].extension));
  if (byExtension) return byExtension;
  return KINDS.find((kind) => file.type === RESUME_FILE_TYPES[kind].mimeType) ?? null;
}

export function isLegacyWordFile(file: Pick<File, 'name' | 'type'>): boolean {
  return file.name.toLowerCase().endsWith('.doc') || file.type === 'application/msword';
}

// Stored resumes with a missing or unknown type display as PDF.
export function kindFromContentType(contentType: string | undefined): ResumeFileKind {
  return KINDS.find((kind) => RESUME_FILE_TYPES[kind].mimeType === contentType) ?? 'pdf';
}