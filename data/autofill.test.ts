import { describe, expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { matchFields, toReviewFields } from "./autofillEngine.js";
import { extractResumeContact } from "./resumeContactExtractor.js";
import { extractPDFText } from "./pdfParser.js";

describe("autofill matcher", () => {
  it("uses backend profile names and combines explicit name parts", () => {
    const matches = matchFields(
      { firstname: "Alex", lastname: "Rivera", email: "alex@example.com",
        phoneNumber: "+18505551234" },
      [
        { id: "name", label: "Full name" },
        { id: "email", label: "Email address", type: "email" },
        { id: "phone", label: "Mobile number", type: "tel" },
      ],
    );
    expect(matches.map(match => match.value)).toEqual([
      "Alex Rivera", "alex@example.com", "+18505551234",
    ]);
    expect(matches.every(match => match.status === "matched")).toBe(true);
  });

  it("handles camelCase, placeholders, and autocomplete", () => {
    const matches = matchFields(
      { firstname: "Alex", email: "alex@example.com" },
      [
        { id: "first", name: "firstName" },
        { id: "email", autocomplete: "section-applicant email" },
        { id: "placeholder", placeholder: "Email address" },
      ],
    );
    expect(matches.map(match => match.status)).toEqual([
      "matched", "matched", "matched",
    ]);
  });

  it("preserves existing values and skips noneditable fields", () => {
    const matches = matchFields({ email: "alex@example.com" }, [
      { id: "existing", label: "Email", currentValue: "other@example.com" },
      { id: "disabled", label: "Email", disabled: true },
      { id: "readonly", label: "Email", readOnly: true },
    ]);
    expect(matches.every(match => match.status === "skipped")).toBe(true);
    expect(matches.every(match => match.value === null)).toBe(true);
  });

  it("does not guess answers or another person's contact information", () => {
    const matches = matchFields(
      { fullName: "Alex Rivera", email: "alex@example.com" },
      [
        { id: "salary", label: "Expected salary" },
        { id: "reference", label: "Reference email", type: "email" },
        { id: "emergency", label: "Emergency contact name" },
        { id: "authorization", label: "Work authorization" },
      ],
    );
    expect(matches.every(match => match.status === "unmatched")).toBe(true);
  });

  it("distinguishes missing information from conflicting metadata", () => {
    const matches = matchFields({}, [
      { id: "phone", label: "Phone number" },
      { id: "conflict", label: "Email", name: "phoneNumber" },
      { id: "wrong-type", label: "Email", type: "tel" },
      { id: "url", label: "Full name", type: "url" },
    ]);
    expect(matches.map(match => match.status)).toEqual([
      "missing", "review", "review", "review",
    ]);
  });

  it("skips submit buttons and unsupported controls", () => {
    const matches = matchFields({ fullName: "Alex Rivera" }, [
      { id: "submit", label: "Name", type: "submit" },
      { id: "consent", label: "Name", type: "checkbox" },
      { id: "hidden", label: "Name", type: "hidden" },
    ]);
    expect(matches.every(match => match.status === "skipped")).toBe(true);
  });

  it("rejects duplicate or empty field IDs", () => {
    expect(() => matchFields({}, [{ id: "same" }, { id: "same" }]))
      .toThrow("unique, non-empty IDs");
    expect(() => matchFields({}, [{ id: " " }]))
      .toThrow("unique, non-empty IDs");
  });

  it("does not guess first and last names from a full name", () => {
    const matches = matchFields({ fullName: "Alex Rivera" }, [
      { id: "first", label: "First name" },
    ]);
    expect(matches[0].status).toBe("missing");
  });

  it("does not mutate input objects", () => {
    const contact = Object.freeze({ email: " alex@example.com " });
    const field = Object.freeze({ id: "email", label: "Email" });
    const matches = matchFields(contact, Object.freeze([field]));
    expect(matches[0].value).toBe("alex@example.com");
    expect(contact.email).toBe(" alex@example.com ");
    expect(field).toEqual({ id: "email", label: "Email" });
  });

  it("adapts only matched values to the existing review display shape", () => {
    const matches = matchFields({ email: "alex@example.com" }, [
      { id: "email", label: "Email" },
      { id: "salary", label: "Expected salary" },
    ]);
    expect(toReviewFields(matches)).toEqual({
      fields: [{ label: "Email", value: "alex@example.com" }],
    });
  });
});

describe("resume contact extraction", () => {
  it("connects extracted text to field matching", () => {
    const contact = extractResumeContact([{
      pageNumber: 1,
      lines: ["Alex Rivera", "alex@example.com",
        "https://www.linkedin.com/in/alex-rivera",
        "https://github.com/alex-rivera"],
    }]);
    expect(contact).toEqual({
      email: "alex@example.com",
      linkedinUrl: "https://linkedin.com/in/alex-rivera",
      githubUrl: "https://github.com/alex-rivera",
    });
    const matches = matchFields(contact, [
      { id: "email", label: "Email address", type: "email" },
    ]);
    expect(matches[0].value).toBe("alex@example.com");
  });

  it("leaves multiple distinct emails and profile URLs absent", () => {
    const contact = extractResumeContact([{
      pageNumber: 1,
      lines: ["alex@example.com", "reference@example.com",
        "https://github.com/alex", "https://github.com/reference"],
    }]);
    expect(contact.email).toBeUndefined();
    expect(contact.githubUrl).toBeUndefined();
  });

  it("accepts repeated identical contact information across pages", () => {
    const contact = extractResumeContact([
      { pageNumber: 1, lines: ["alex@example.com"] },
      { pageNumber: 2, lines: ["alex@example.com"] },
    ]);
    expect(contact.email).toBe("alex@example.com");
  });

  it("rejects lookalike domains and repository URLs", () => {
    const contact = extractResumeContact([{
      pageNumber: 1,
      lines: ["https://github.com.example.org/alex",
        "https://github.com/alex/project"],
    }]);
    expect(contact.githubUrl).toBeUndefined();
  });

  it("returns no guessed information for empty input", () => {
    expect(extractResumeContact([])).toEqual({});
  });

  it("accepts the existing PDF fixture through the pipeline", async () => {
    const buffer = await readFile(new URL("./fixtures/alex.pdf", import.meta.url));
    const pages = await extractPDFText({
      size: buffer.length,
      arrayBuffer: async () => Uint8Array.from(buffer).buffer,
    });
    const contact = extractResumeContact(pages);
    const matches = matchFields(contact, [
      { id: "email", label: "Email", type: "email" },
    ]);
    // A pipeline smoke check; exact values are checked in synthetic tests above.
    expect(pages.length).toBeGreaterThan(0);
    expect(matches[0].status).toBe(contact.email ? "matched" : "missing");
    expect(matches[0].value).toBe(contact.email ?? null);
  });
});
