import { beforeEach, describe, expect, it } from "vitest";
import {
  getFieldLabel,
  getFieldDescription,
  getFieldOptions,
  extractFieldData,
  scanFormFields,
} from "./formFieldDetector.js";

describe("Matchob Form Field Detector", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  // 1. Standard HTML label
  it("detects a label linked by for and id", () => {
    document.body.innerHTML = `
      <label for="firstName">First Name</label>
      <input id="firstName" type="text" />
    `;
    const input = document.querySelector("input")!;
    expect(getFieldLabel(input)).toBe("First Name");
  });

  // 2. aria-label
  it("detects aria-label", () => {
    document.body.innerHTML = `
      <input id="linkedin" type="url" aria-label="LinkedIn Profile URL" />
    `;
    const input = document.querySelector("input")!;
    expect(getFieldLabel(input)).toBe("LinkedIn Profile URL");
  });

  // 3. aria-labelledby
  it("resolves aria-labelledby", () => {
    document.body.innerHTML = `
      <span id="question">Current Job Title</span>
      <input id="jobTitle" type="text" aria-labelledby="question" />
    `;
    const input = document.querySelector("input")!;
    expect(getFieldLabel(input)).toBe("Current Job Title");
  });

  // 4. Accessible-name precedence
  it("prioritizes aria-labelledby over aria-label and HTML label", () => {
    document.body.innerHTML = `
      <span id="preferredLabel">Preferred Name</span>
      <label for="name">Legal Name</label>
      <input id="name" aria-label="Full Name" aria-labelledby="preferredLabel" />
    `;
    const input = document.querySelector("input")!;
    expect(getFieldLabel(input)).toBe("Preferred Name");
  });

  // 5. Unlabeled input
  it("uses name/id as a fallback when an accessible label is absent", () => {
    document.body.innerHTML = `
      <input id="firstName" name="firstName" type="text" />
    `;
    const input = document.querySelector("input")!;
    expect(getFieldLabel(input)).toBe("firstName");
  });

  // 6. Placeholder fallback
  it("uses placeholder as a fallback accessible label", () => {
    document.body.innerHTML = `
      <input id="phone" type="tel" placeholder="Enter your phone number" />
    `;
    const input = document.querySelector("input")!;
    expect(getFieldLabel(input)).toBe("Enter your phone number");
  });

  // 7. Description supplied through aria-describedby
  it("extracts a field description", () => {
    document.body.innerHTML = `
      <label for="resume">Resume</label>
      <p id="instructions">Upload your resume as a PDF.</p>
      <input id="resume" type="file" aria-describedby="instructions" />
    `;
    const input = document.querySelector("input")!;
    expect(getFieldDescription(input)).toBe("Upload your resume as a PDF.");
  });

  // 8. No description
  it("handles a field with no description", () => {
    document.body.innerHTML = `
      <label for="email">Email</label>
      <input id="email" type="email" />
    `;
    const input = document.querySelector("input")!;
    expect(getFieldDescription(input)).toBe("");
  });

  // 9. Field metadata
  it("extracts input type and identifiers", () => {
    document.body.innerHTML = `
      <input id="email" name="email" type="email" />
    `;
    const input = document.querySelector("input")!;
    const result = extractFieldData(input, 0);
    expect(result.fieldID).toBe("email");
    expect(result.inputType).toBe("email");
    expect(result.fieldType).toBe("input");
    expect(result.name).toBe("email");
  });

  // 10. Required input
  it("detects a required field", () => {
    document.body.innerHTML = `<input id="email" type="email" required />`;
    const input = document.querySelector("input")!;
    expect(extractFieldData(input, 0).required).toBe(true);
  });

  // 11. Optional input
  it("detects an optional field", () => {
    document.body.innerHTML = `<input id="middleName" type="text" />`;
    const input = document.querySelector("input")!;
    expect(extractFieldData(input, 0).required).toBe(false);
  });

  // 12. Native dropdown choices
  // This test assumes getFieldOptions returns string[] of option text.
  // If your implementation returns {value, label} objects, adapt this expectation.
  it("extracts select option labels", () => {
    document.body.innerHTML = `
      <select id="degree" name="degree">
        <option value="">Select One</option>
        <option value="hs">High School</option>
        <option value="bs">Bachelor's Degree</option>
        <option value="ms">Master's Degree</option>
      </select>
    `;
    const select = document.querySelector("select")!;
    expect(getFieldOptions(select)).toEqual([
      "Select One",
      "High School",
      "Bachelor's Degree",
      "Master's Degree",
    ]);
  });

  // 13. Textarea
  it("extracts a textarea's type and label", () => {
    document.body.innerHTML = `
      <label for="motivation">Why do you want to work here?</label>
      <textarea id="motivation" name="motivation"></textarea>
    `;
    const textarea = document.querySelector("textarea")!;
    const result = extractFieldData(textarea, 0);
    expect(result.fieldType).toBe("textarea");
    expect(result.label).toBe("Why do you want to work here?");
  });

  // 14. Hidden inputs should not be considered user-fillable questions
  it("does not include hidden inputs when scanning", () => {
    document.body.innerHTML = `
      <input type="hidden" name="csrfToken" value="12345" />
      <label for="name">Full Name</label>
      <input id="name" name="name" />
    `;
    const fields = scanFormFields();
    expect(fields).toHaveLength(1);
    expect(fields[0].name).toBe("name");
  });

  // 15. Re-scanning after dynamic DOM changes
  it("detects fields added after the initial scan", () => {
    document.body.innerHTML = `
      <label for="firstName">First Name</label>
      <input id="firstName" name="firstName" />
    `;
    expect(scanFormFields()).toHaveLength(1);

    document.body.insertAdjacentHTML(
      "beforeend",
      `<label for="lastName">Last Name</label>
       <input id="lastName" name="lastName" />`,
    );

    const updated = scanFormFields();
    expect(updated).toHaveLength(2);
    expect(updated.some((field) => field.name === "lastName")).toBe(true);
  });


// ============================================================
// EXPANDED COVERAGE — target behaviors for Matchob.
// Failures here may reveal missing features, not broken Vitest.
// ============================================================

describe("Additional accessible-name cases", () => {
  it("reads a label wrapping an input", () => {
    document.body.innerHTML = `<label>Phone Number <input name="phone" type="tel"></label>`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Phone Number");
  });

  it("combines multiple aria-labelledby references", () => {
    document.body.innerHTML = `<span id="a">Preferred</span><span id="b">Location</span><input aria-labelledby="a b">`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Preferred Location");
  });

  it("uses aria-label in preference to a visible HTML label", () => {
    document.body.innerHTML = `<label for="x">Old text</label><input id="x" aria-label="Updated text">`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Updated text");
  });

  it("combines multiple associated HTML labels", () => {
    document.body.innerHTML = `<label for="x">Work</label><label for="x">Email</label><input id="x">`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Work Email");
  });

  it("reads a title attribute when no higher priority name exists", () => {
    document.body.innerHTML = `<input title="Professional Website">`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Professional Website");
  });

  it("uses the visible label ahead of placeholder text", () => {
    document.body.innerHTML = `<label for="x">Email Address</label><input id="x" placeholder="name@example.com">`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Email Address");
  });

  it("handles an empty aria-label when a linked label exists", () => {
    document.body.innerHTML = `<label for="x">First Name</label><input id="x" aria-label="">`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("First Name");
  });

  it("does not include placeholder text in an aria-labelled input name", () => {
    document.body.innerHTML = `<input aria-label="Portfolio URL" placeholder="https://example.com">`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Portfolio URL");
  });

  it("reads a label even when the element is outside a form", () => {
    document.body.innerHTML = `<label for="x">Graduation Year</label><div><input id="x"></div>`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Graduation Year");
  });

  it("handles Unicode in field labels", () => {
    document.body.innerHTML = `<label for="x">Prénom / 名字</label><input id="x">`;
    expect(getFieldLabel(document.querySelector("input")!)).toBe("Prénom / 名字");
  });
});

describe("Additional accessible descriptions", () => {
  it("resolves multiple aria-describedby elements", () => {
    document.body.innerHTML = `<small id="a">PDF only.</small><small id="b">Maximum 5 MB.</small><input aria-describedby="a b">`;
    expect(getFieldDescription(document.querySelector("input")!)).toBe("PDF only. Maximum 5 MB.");
  });

  it("reads aria-description", () => {
    document.body.innerHTML = `<input aria-label="Resume" aria-description="Upload a current resume">`;
    expect(getFieldDescription(document.querySelector("input")!)).toBe("Upload a current resume");
  });

  it("prioritizes aria-describedby over aria-description", () => {
    document.body.innerHTML = `<span id="d">Use a PDF.</span><input aria-description="Other guidance" aria-describedby="d">`;
    expect(getFieldDescription(document.querySelector("input")!)).toBe("Use a PDF.");
  });

  it("does not confuse a label with its description", () => {
    document.body.innerHTML = `<label for="x">Resume</label><p id="h">PDF only</p><input id="x" aria-describedby="h">`;
    const input = document.querySelector("input")!;
    expect(getFieldLabel(input)).toBe("Resume");
    expect(getFieldDescription(input)).toBe("PDF only");
  });

  it("handles description containing Unicode", () => {
    document.body.innerHTML = `<span id="d">Téléversez votre CV</span><input aria-describedby="d">`;
    expect(getFieldDescription(document.querySelector("input")!)).toBe("Téléversez votre CV");
  });
});

describe("Additional field metadata", () => {
  it.each([
    ["text", "text"], ["email", "email"], ["tel", "tel"],
    ["url", "url"], ["number", "number"], ["date", "date"],
    ["file", "file"], ["checkbox", "checkbox"], ["radio", "radio"],
    ["password", "password"], ["search", "search"],
  ])("returns inputType=%s", (type, expected) => {
    document.body.innerHTML = `<input id="x" type="${type}">`;
    expect(extractFieldData(document.querySelector("input")!, 0).inputType).toBe(expected);
  });

  it("defaults an input with no type to text", () => {
    document.body.innerHTML = `<input id="x">`;
    expect(extractFieldData(document.querySelector("input")!, 0).inputType).toBe("text");
  });

  it("extracts a placeholder", () => {
    document.body.innerHTML = `<input id="x" placeholder="City, State">`;
    expect(extractFieldData(document.querySelector("input")!, 0).placeholder).toBe("City, State");
  });

  it("returns an empty placeholder for select controls", () => {
    document.body.innerHTML = `<select id="x"><option>Choose</option></select>`;
    expect(extractFieldData(document.querySelector("select")!, 0).placeholder).toBe("");
  });

  it("returns an empty name when the HTML name attribute is absent", () => {
    document.body.innerHTML = `<input id="x">`;
    expect(extractFieldData(document.querySelector("input")!, 0).name).toBe("");
  });

  it("uses an existing field ID", () => {
    document.body.innerHTML = `<textarea id="coverLetter"></textarea>`;
    expect(extractFieldData(document.querySelector("textarea")!, 4).fieldID).toBe("coverLetter");
  });

  it("creates a fallback ID for a field without one", () => {
    document.body.innerHTML = `<input name="zip">`;
    expect(extractFieldData(document.querySelector("input")!, 3).fieldID).toBe("field-3");
  });

  it("returns select as the field type", () => {
    document.body.innerHTML = `<select id="x"><option>One</option></select>`;
    expect(extractFieldData(document.querySelector("select")!, 0).fieldType).toBe("select");
  });

  it("returns textarea as the input type", () => {
    document.body.innerHTML = `<textarea id="x"></textarea>`;
    expect(extractFieldData(document.querySelector("textarea")!, 0).inputType).toBe("textarea");
  });

  it("detects a required select", () => {
    document.body.innerHTML = `<select id="x" required><option>One</option></select>`;
    expect(extractFieldData(document.querySelector("select")!, 0).required).toBe(true);
  });

  it("detects a required textarea", () => {
    document.body.innerHTML = `<textarea required></textarea>`;
    expect(extractFieldData(document.querySelector("textarea")!, 0).required).toBe(true);
  });

  it("includes description in the extracted object", () => {
    document.body.innerHTML = `<span id="help">Include country code</span><input aria-label="Phone" aria-describedby="help">`;
    expect(extractFieldData(document.querySelector("input")!, 0).description).toBe("Include country code");
  });
});

describe("Select option extraction", () => {
  it("returns an empty array for a select without options", () => {
    document.body.innerHTML = `<select id="x"></select>`;
    expect(getFieldOptions(document.querySelector("select")!)).toEqual([]);
  });

  it("returns an empty array for text inputs", () => {
    document.body.innerHTML = `<input id="x" type="text">`;
    expect(getFieldOptions(document.querySelector("input")!)).toEqual([]);
  });

  it("returns an empty array for textareas", () => {
    document.body.innerHTML = `<textarea id="x"></textarea>`;
    expect(getFieldOptions(document.querySelector("textarea")!)).toEqual([]);
  });

  it("preserves the order of dropdown choices", () => {
    document.body.innerHTML = `<select><option>Remote</option><option>Hybrid</option><option>On-site</option></select>`;
    expect(getFieldOptions(document.querySelector("select")!)).toEqual(["Remote", "Hybrid", "On-site"]);
  });

  it("uses visible option text, not its machine value", () => {
    document.body.innerHTML = `<select><option value="bs">Bachelor's Degree</option></select>`;
    expect(getFieldOptions(document.querySelector("select")!)).toEqual(["Bachelor's Degree"]);
  });

  it("includes choices inside optgroup elements", () => {
    document.body.innerHTML = `<select><optgroup label="US"><option>Florida</option><option>Georgia</option></optgroup></select>`;
    expect(getFieldOptions(document.querySelector("select")!)).toEqual(["Florida", "Georgia"]);
  });

  it("preserves option text with Unicode", () => {
    document.body.innerHTML = `<select><option>Español</option><option>Tiếng Việt</option></select>`;
    expect(getFieldOptions(document.querySelector("select")!)).toEqual(["Español", "Tiếng Việt"]);
  });

  it("keeps a blank prompt option when it exists", () => {
    document.body.innerHTML = `<select><option value="">Select one</option><option>Yes</option></select>`;
    expect(getFieldOptions(document.querySelector("select")!)).toEqual(["Select one", "Yes"]);
  });
});

describe("Full-page field scanning", () => {
  it("returns an array when no form controls exist", () => {
    document.body.innerHTML = `<h1>Apply today</h1><p>Welcome!</p>`;
    expect(scanFormFields()).toEqual([]);
  });

  it("detects multiple text inputs", () => {
    document.body.innerHTML = `<input name="first"><input name="last"><input name="email">`;
    expect(scanFormFields().map(f => f.name)).toEqual(["first", "last", "email"]);
  });

  it("detects fields in separate forms", () => {
    document.body.innerHTML = `<form><input name="first"></form><form><input name="second"></form>`;
    expect(scanFormFields().map(f => f.name)).toEqual(["first", "second"]);
  });

  it("detects controls that are not nested inside form tags", () => {
    document.body.innerHTML = `<div><input name="city"><textarea name="summary"></textarea></div>`;
    expect(scanFormFields().map(f => f.name)).toEqual(["city", "summary"]);
  });

  it("detects a mix of input, select, and textarea", () => {
    document.body.innerHTML = `<input name="email"><select name="degree"><option>BS</option></select><textarea name="about"></textarea>`;
    expect(scanFormFields().map(f => f.name)).toEqual(["email", "degree", "about"]);
  });

  it("does not include submit buttons", () => {
    document.body.innerHTML = `<input name="email"><input type="submit" value="Apply">`;
    expect(scanFormFields().map(f => f.name)).toEqual(["email"]);
  });

  it("does not include reset buttons", () => {
    document.body.innerHTML = `<input name="email"><input type="reset" value="Clear">`;
    expect(scanFormFields().map(f => f.name)).toEqual(["email"]);
  });

  it("does not include button-type inputs", () => {
    document.body.innerHTML = `<input name="email"><input type="button" value="Help">`;
    expect(scanFormFields().map(f => f.name)).toEqual(["email"]);
  });

  it("does not include controls hidden by the hidden attribute", () => {
    document.body.innerHTML = `<input name="hidden" hidden><input name="visible">`;
    expect(scanFormFields().map(f => f.name)).toEqual(["visible"]);
  });

  it("does not include fields inside hidden containers", () => {
    document.body.innerHTML = `<div hidden><input name="secret"></div><input name="visible">`;
    expect(scanFormFields().map(f => f.name)).toEqual(["visible"]);
  });

  it("does not include disabled controls", () => {
    document.body.innerHTML = `<input name="disabled" disabled><input name="enabled">`;
    expect(scanFormFields().map(f => f.name)).toEqual(["enabled"]);
  });

  it("does not include controls inside disabled fieldsets", () => {
    document.body.innerHTML = `<fieldset disabled><input name="old"></fieldset><input name="active">`;
    expect(scanFormFields().map(f => f.name)).toEqual(["active"]);
  });

  it("detects checkbox questions", () => {
    document.body.innerHTML = `<label><input type="checkbox" name="agree">I agree</label>`;
    const fields = scanFormFields();
    expect(fields).toHaveLength(1);
    expect(fields[0].inputType).toBe("checkbox");
    expect(fields[0].label).toBe("I agree");
  });

  it("detects every radio choice individually", () => {
    document.body.innerHTML = `<label><input type="radio" name="remote" value="yes">Yes</label><label><input type="radio" name="remote" value="no">No</label>`;
    const fields = scanFormFields();
    expect(fields).toHaveLength(2);
    expect(fields.map(f => f.label)).toEqual(["Yes", "No"]);
  });

  it("re-scanning an unchanged DOM does not accumulate duplicates", () => {
    document.body.innerHTML = `<input name="first"><input name="second">`;
    expect(scanFormFields()).toHaveLength(2);
    expect(scanFormFields()).toHaveLength(2);
    expect(scanFormFields()).toHaveLength(2);
  });

  it("removes fields from results after they are removed from DOM", () => {
    document.body.innerHTML = `<input id="a" name="first"><input id="b" name="second">`;
    expect(scanFormFields()).toHaveLength(2);
    document.getElementById("b")!.remove();
    expect(scanFormFields().map(f => f.name)).toEqual(["first"]);
  });

  it("updates metadata after a label changes", () => {
    document.body.innerHTML = `<label for="x" id="label">Email</label><input id="x" name="email">`;
    expect(scanFormFields()[0].label).toBe("Email");
    document.getElementById("label")!.textContent = "Work Email";
    expect(scanFormFields()[0].label).toBe("Work Email");
  });

  it("does not change field values during scanning", () => {
    document.body.innerHTML = `<input name="first" value="Ada"><textarea name="message">Hello</textarea>`;
    scanFormFields();
    expect((document.querySelector("input") as HTMLInputElement).value).toBe("Ada");
    expect((document.querySelector("textarea") as HTMLTextAreaElement).value).toBe("Hello");
  });

  it("does not submit forms during scanning", () => {
    document.body.innerHTML = `<form id="job"><input name="email"></form>`;
    let submitted = false;
    document.querySelector("form")!.addEventListener("submit", e => { e.preventDefault(); submitted = true; });
    scanFormFields();
    expect(submitted).toBe(false);
  });

  it("detects one field with a label and full metadata", () => {
    document.body.innerHTML = `<label for="portfolio">Portfolio</label><small id="hint">Paste a public URL</small><input id="portfolio" name="portfolio" type="url" placeholder="https://example.com" aria-describedby="hint" required>`;
    expect(scanFormFields()).toEqual(expect.arrayContaining([
      expect.objectContaining({
        fieldID: "portfolio", name: "portfolio", label: "Portfolio",
        description: "Paste a public URL", inputType: "url",
        placeholder: "https://example.com", required: true,
      }),
    ]));
  });

  it("handles a realistic job application with multiple control types", () => {
    document.body.innerHTML = `
      <form id="application">
        <label for="first">First name</label><input id="first" name="first" required>
        <label for="email">Email</label><input id="email" name="email" type="email" required>
        <label for="phone">Phone</label><input id="phone" name="phone" type="tel">
        <label for="resume">Resume</label><input id="resume" name="resume" type="file">
        <label for="degree">Degree</label>
        <select id="degree" name="degree"><option value="">Choose</option><option>BS</option></select>
        <label for="cover">Cover letter</label><textarea id="cover" name="cover"></textarea>
        <label><input name="consent" type="checkbox">I consent</label>
        <input type="hidden" name="csrf" value="token">
        <button type="submit">Submit</button>
      </form>
    `;
    const fields = scanFormFields();
    expect(fields.map(f => f.name)).toEqual(["first", "email", "phone", "resume", "degree", "cover", "consent"]);
    expect(fields.find(f => f.name === "degree")?.options).toEqual(["Choose", "BS"]);
    expect(fields.find(f => f.name === "email")?.required).toBe(true);
  });
});


});