// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from "vitest";
import {
  getFieldLabel, getFieldDescription, getFieldOptions,
  extractFieldData, scanFormFields,
} from "./formFieldDetector.js";

const mount = (html: string) => { document.body.innerHTML = html; };
const input = () => document.querySelector("input")!;
const names = () => scanFormFields().map(field => field.name);

beforeEach(() => { document.body.innerHTML = ""; });

describe("Accessible names", () => {
  it.each([
    ["linked HTML label", '<label for="x">First Name</label><input id="x">', "First Name"],
    ["wrapping label", '<label>Phone <input name="phone"></label>', "Phone"],
    ["aria-label", '<input aria-label="LinkedIn URL">', "LinkedIn URL"],
    ["aria-labelledby", '<span id="a">Job Title</span><input aria-labelledby="a">', "Job Title"],
    ["multiple references", '<span id="a">Work</span><span id="b">Email</span><input aria-labelledby="a b">', "Work Email"],
    ["ARIA precedence", '<span id="a">Preferred</span><label for="x">Legal</label><input id="x" aria-label="Full" aria-labelledby="a">', "Preferred"],
    ["placeholder fallback", '<input placeholder="Enter phone">', "Enter phone"],
    ["name fallback", '<input name="firstName">', "firstName"],
    ["id fallback", '<input id="lastName">', "lastName"],
    ["Unicode", '<label for="x">Prénom / 名字</label><input id="x">', "Prénom / 名字"],
  ])("reads %s", (_case, html, expected) => {
    mount(html);
    expect(getFieldLabel(input())).toBe(expected);
  });
});

describe("Descriptions", () => {
  it.each([
    ["aria-describedby", '<p id="h">PDF only</p><input aria-describedby="h">', "PDF only"],
    ["multiple references", '<p id="a">PDF only.</p><p id="b">Max 5 MB.</p><input aria-describedby="a b">', "PDF only. Max 5 MB."],
    ["aria-description", '<input aria-description="Use a recent resume">', "Use a recent resume"],
    ["no description", '<input aria-label="Email">', ""],
  ])("reads %s", (_case, html, expected) => {
    mount(html);
    expect(getFieldDescription(input())).toBe(expected);
  });
});

describe("Field metadata", () => {
  it.each(["text", "email", "tel", "url", "number", "date", "file", "radio", "checkbox"])(
    "extracts type=%s", type => {
      mount(`<input id="x" type="${type}">`);
      expect(extractFieldData(input(), 0).inputType).toBe(type);
    },
  );

  it("returns label, ID, name, placeholder, description and required status", () => {
    mount('<label for="x">Portfolio</label><p id="d">Public link</p><input id="x" name="portfolio" type="url" placeholder="https://example.com" aria-describedby="d" required>');
    expect(extractFieldData(input(), 0)).toEqual(expect.objectContaining({
      fieldID: "x", fieldType: "input", inputType: "url", name: "portfolio",
      label: "Portfolio", description: "Public link", placeholder: "https://example.com", required: true,
    }));
  });

  it("creates fallback IDs", () => {
    mount('<input name="zip">');
    expect(extractFieldData(input(), 3).fieldID).toBe("field-3");
  });

  it("extracts textarea fields", () => {
    mount('<label for="q">Why us?</label><textarea id="q" name="motivation"></textarea>');
    expect(extractFieldData(document.querySelector("textarea")!, 0)).toEqual(expect.objectContaining({
      fieldType: "textarea", inputType: "textarea", label: "Why us?", name: "motivation",
    }));
  });

  it.each([
    ["native required", '<input required>', true],
    ["ARIA required", '<input aria-required="true">', true],
    ["optional", '<input>', false],
    ["ARIA explicitly false", '<input aria-required="false">', false],
  ])("handles %s", (_case, html, required) => {
    mount(html);
    expect(extractFieldData(input(), 0).required).toBe(required);
  });
});

describe("Dropdown options", () => {
  it("returns visible option labels, including optgroup children", () => {
    mount('<select><option value="">Choose</option><optgroup label="Degrees"><option value="bs">Bachelor\'s</option><option value="ms">Master\'s</option></optgroup></select>');
    expect(getFieldOptions(document.querySelector("select")!)).toEqual(["Choose", "Bachelor's", "Master's"]);
  });

  it("returns [] for non-select fields", () => {
    mount('<input><textarea></textarea>');
    expect(getFieldOptions(input())).toEqual([]);
    expect(getFieldOptions(document.querySelector("textarea")!)).toEqual([]);
  });

  it("reflects options added after the first scan", () => {
    mount('<select name="degree"><option>BS</option></select>');
    const select = document.querySelector("select")!;
    expect(getFieldOptions(select)).toEqual(["BS"]);
    select.add(new Option("MS", "ms"));
    expect(getFieldOptions(select)).toEqual(["BS", "MS"]);
  });
});

describe("Scanning and visibility", () => {
  it.each([
    ["empty page", '<h1>Apply</h1>', []],
    ["mixed fields", '<input name="email"><select name="degree"></select><textarea name="about"></textarea>', ["email", "degree", "about"]],
    ["resume upload", '<input type="file" name="resume">', ["resume"]],
    ["non-data buttons", '<input name="email"><input type="submit"><input type="reset"><input type="button"><input type="image">', ["email"]],
    ["hidden type", '<input name="token" type="hidden"><input name="email">', ["email"]],
    ["hidden attribute", '<input name="secret" hidden><input name="email">', ["email"]],
    ["hidden parent", '<div hidden><input name="secret"></div><input name="email">', ["email"]],
    ["disabled input", '<input name="off" disabled><input name="on">', ["on"]],
    ["disabled fieldset", '<fieldset disabled><input name="off"></fieldset><input name="on">', ["on"]],
    ["inline display none", '<input style="display:none" name="off"><input name="on">', ["on"]],
    ["hidden CSS parent", '<div style="display:none"><input name="off"></div><input name="on">', ["on"]],
    ["visibility hidden", '<textarea style="visibility:hidden" name="off"></textarea><input name="on">', ["on"]],
    ["ARIA hidden", '<div aria-hidden="true"><input name="off"></div><input name="on">', ["on"]],
    ["inert parent", '<div inert><input name="off"></div><input name="on">', ["on"]],
    ["radio and checkbox", '<input type="radio" name="choice"><input type="radio" name="choice"><input type="checkbox" name="consent">', ["choice", "choice", "consent"]],
  ])("handles %s", (_case, html, expected) => {
    mount(html);
    expect(names()).toEqual(expected);
  });

  it("excludes fields hidden by a CSS class", () => {
    const style = document.createElement("style");
    style.textContent = ".hide-test-field { display: none; }";
    document.head.appendChild(style);
    try {
      mount('<input name="off" class="hide-test-field"><input name="on">');
      expect(names()).toEqual(["on"]);
    } finally { style.remove(); }
  });

  it("finds fields added, removed, or revealed after a rescan", () => {
    mount('<input name="first"><div id="step" style="display:none"><input name="second"></div>');
    expect(names()).toEqual(["first"]);
    document.getElementById("step")!.setAttribute("style", "display:block");
    expect(names()).toEqual(["first", "second"]);
    document.querySelector('input[name="first"]')!.remove();
    expect(names()).toEqual(["second"]);
  });

  it("does not duplicate entries across repeated scans", () => {
    mount('<input name="a"><input name="b">');
    expect(names()).toEqual(["a", "b"]);
    expect(names()).toEqual(["a", "b"]);
  });

  it("does not change values or submit a form", () => {
    mount('<form><input name="email" value="test@example.com"><textarea name="note">Hi</textarea></form>');
    let submitted = false;
    document.querySelector("form")!.addEventListener("submit", e => { e.preventDefault(); submitted = true; });
    scanFormFields();
    expect(input().value).toBe("test@example.com");
    expect(document.querySelector("textarea")!.value).toBe("Hi");
    expect(submitted).toBe(false);
  });
});

// Sensitive field filtering
describe("Sensitive field filtering", () => {
  it.each([
    ["SSN", '<input name="ssn">'],
    ["Date of birth", '<input name="dateOfBirth">'],
    ["Password", '<input type="password">'],
    ["Credit card", '<input autocomplete="cc-number">'],
    ["EEO", '<input name="eeoQuestion">'],
    ["Race", '<select name="race"></select>'],
    ["Ethnicity", '<select name="ethnicity"></select>'],
    ["Gender", '<select name="gender"></select>'],
    ["Disability", '<select name="disability_status"></select>'],
    ["Veteran", '<select name="veteranStatus"></select>'],
    ["Salary", '<input name="desiredSalary">'],
    ["Compensation", '<input aria-label="Expected compensation">'],
  ])("excludes %s fields", (_case, html) => {
    mount(`${html}<input name="email">`);
    expect(names()).toEqual(["email"]);
  });

  it("does not exclude fields containing partial keyword matches", () => {
    mount(`
      <input name="adobeExperience">
      <input name="traceability">
      <input name="email">
    `);

    expect(names()).toEqual([
      "adobeExperience",
      "traceability",
      "email"
    ]);
  });
});