import type {
  ContactKey,
  DetectedField,
  FieldMatch,
  MatchStatus,
  ResumeContact,
} from "./autofillTypes.js";

const aliases: Record<ContactKey, readonly string[]> = {
  firstname: ["first name", "firstname", "given name"],
  lastname: ["last name", "lastname", "family name", "surname"],
  fullName: ["full name", "applicant name", "your name", "name"],
  email: ["email", "email address", "contact email"],
  phoneNumber: [
    "phone", "phone number", "telephone", "mobile", "mobile number",
    "contact number",
  ],
  linkedinUrl: ["linkedin", "linkedin url", "linkedin profile"],
  githubUrl: ["github", "github url", "github profile"],
};

const autocompleteKeys: Readonly<Partial<Record<string, ContactKey>>> = {
  name: "fullName",
  "given-name": "firstname",
  "family-name": "lastname",
  email: "email",
  tel: "phoneNumber",
};

function normalize(value: string): string {
  return value
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function findCandidates(field: DetectedField): Set<ContactKey> {
  const candidates = new Set<ContactKey>();
  const signals = [field.label, field.name, field.placeholder]
    .filter((value): value is string => Boolean(value?.trim()))
    .map(normalize);

  for (const key of Object.keys(aliases) as ContactKey[]) {
    if (signals.some(signal => aliases[key].includes(signal))) {
      candidates.add(key);
    }
  }

  for (const token of (field.autocomplete ?? "").toLowerCase().split(/\s+/)) {
    const key = Object.hasOwn(autocompleteKeys, token)
      ? autocompleteKeys[token]
      : undefined;
    if (key) candidates.add(key);
  }

  // Input type alone does not establish whose contact information is requested.
  return candidates;
}

function getValue(contact: ResumeContact, key: ContactKey): string | undefined {
  const direct = contact[key]?.trim();
  if (direct) return direct;

  if (key === "fullName") {
    const first = contact.firstname?.trim();
    const last = contact.lastname?.trim();
    if (first && last) return `${first} ${last}`;
  }
  
  return undefined;
}

/** Returns proposed values only. Does not fill a page or submit a form. */
export function matchFields(
  contact: ResumeContact,
  fields: readonly DetectedField[],
): FieldMatch[] {
  const ids = new Set<string>();
  for (const field of fields) {
    if (!field.id.trim() || ids.has(field.id)) {
      throw new Error("Detected fields must have unique, non-empty IDs.");
    }
    ids.add(field.id);
  }

  return fields.map(field => {
    const result = (
      status: MatchStatus,
      reason: string,
      key: ContactKey | null = null,
      value: string | null = null,
    ): FieldMatch => ({
      fieldId: field.id,
      label: field.label || field.name || field.id,
      key, value, status, reason,
    });

    if (field.disabled || field.readOnly) {
      return result("skipped", "Field cannot be edited.");
    }
    if (field.currentValue?.trim()) {
      return result("skipped", "Field already contains a value.");
    }

    const type = (field.type ?? "text").toLowerCase();
    if (!["text", "email", "tel", "url"].includes(type)) {
      return result("skipped", "Unsupported field type.");
    }

    const candidates = findCandidates(field);
    if (candidates.size === 0) {
      return result("unmatched", "No recognized field meaning.");
    }
    if (candidates.size > 1) {
      return result("review", "Field metadata has conflicting meanings.");
    }

    const key = [...candidates][0];
    const expectedKey = type === "email" ? "email"
      : type === "tel" ? "phoneNumber" : null;
    if (expectedKey && key !== expectedKey) {
      return result("review", "Input type conflicts with field meaning.");
    }
    if (type === "url" && key !== "linkedinUrl" && key !== "githubUrl") {
      return result("review", "URL input conflicts with field meaning.");
    }

    const value = getValue(contact, key);
    if (!value) return result("missing", `No available value for ${key}.`, key);
    return result("matched", `Matched to ${key}.`, key, value);
  });
}

/** Matches the existing mock's display shape; does not confirm insertion. */
export function toReviewFields(
  matches: readonly FieldMatch[],
): { fields: { label: string; value: string }[] } {
  return {
    fields: matches
      .filter((match): match is FieldMatch & { value: string } =>
        match.status === "matched" && match.value !== null)
      .map(match => ({ label: match.label, value: match.value })),
  };
}
