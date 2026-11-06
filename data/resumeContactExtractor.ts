import type { PDFPage } from "./pdfParser.js";
import type { ResumeContact } from "./autofillTypes.js";

function onlyUnique(
  values: string[],
  key: (value: string) => string = value => value,
): string | undefined {
  const unique = new Map<string, string>();
  for (const value of values) unique.set(key(value), value);
  return unique.size === 1 ? [...unique.values()][0] : undefined;
}

function extractProfileUrl(
  text: string,
  hostname: "linkedin.com" | "github.com",
): string | undefined {
  const candidates = text.match(/https?:\/\/[^\s<>"]+/gi) ?? [];
  const valid: string[] = [];

  for (const candidate of candidates) {
    const cleaned = candidate.replace(/[.,;:!?)\]}]+$/, "");
    try {
      const url = new URL(cleaned);
      const host = url.hostname.toLowerCase().replace(/^www\./, "");
      if (host !== hostname || url.username || url.password || url.port) continue;

      const isProfile = hostname === "linkedin.com"
        ? /^\/in\/[^/]+\/?$/.test(url.pathname)
        : /^\/[a-z0-9-]+\/?$/i.test(url.pathname);
      if (!isProfile) continue;

      url.protocol = "https:";
      url.hostname = hostname;
      url.search = "";
      url.hash = "";
      url.pathname = url.pathname.replace(/\/$/, "");
      valid.push(url.toString());
    } catch {
      // Malformed URLs do not produce fill instructions.
    }
  }
  return onlyUnique(valid);
}

/**
 * Extracts candidate email and explicit profile URLs from existing parser output.
 * Multiple distinct values remain absent. Review extracted data before use.
 * Names and phone numbers must be supplied as structured, confirmed information.
 */
export function extractResumeContact(pages: readonly PDFPage[]): ResumeContact {
  const text = pages.flatMap(page => page.lines).join("\n");
  const emails = text.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi) ?? [];
  const contact: ResumeContact = {};
  const email = onlyUnique(emails, value => value.toLowerCase());
  const linkedinUrl = extractProfileUrl(text, "linkedin.com");
  const githubUrl = extractProfileUrl(text, "github.com");

  if (email) contact.email = email;
  if (linkedinUrl) contact.linkedinUrl = linkedinUrl;
  if (githubUrl) contact.githubUrl = githubUrl;
  return contact;
}
