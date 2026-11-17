/** Contact properties follow the backend profile's naming conventions. */
export interface ResumeContact {
  firstname?: string;
  lastname?: string;
  fullName?: string;
  email?: string;
  phoneNumber?: string;
  linkedinUrl?: string;
  githubUrl?: string;
}

export type ContactKey = keyof ResumeContact;

/** The browser integration supplies metadata, never DOM elements. */
export interface DetectedField {
  id: string;
  label?: string;
  name?: string;
  placeholder?: string;
  type?: string;
  autocomplete?: string;
  currentValue?: string;
  disabled?: boolean;
  readOnly?: boolean;
}

export type MatchStatus =
  | "matched"
  | "missing"
  | "unmatched"
  | "review"
  | "skipped";

export interface FieldMatch {
  fieldId: string;
  label: string;
  key: ContactKey | null;
  value: string | null;
  status: MatchStatus;
  reason: string;
}
