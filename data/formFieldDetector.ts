import {
    computeAccessibleName,
    computeAccessibleDescription
} from "dom-accessibility-api";

type FieldType = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
export interface DetectedField {
    fieldID: string; // Which field it is
    fieldType: string; // what type of field it asks for (text, email, password, etc.)
    label: string; // Usually the question asked
    description: string; // The description of the question, if any
    name: string; // Name of what stores the entry in the form
    placeholder: string; // The placeholder text for the field
    inputType: string; // The type of input (e.g., text, email, password)
    required: boolean; // Whether the field is required
    options?: string[]; // Options for select fields
}
const FIELD_SELECTOR = "input, select, textarea";

function detectFormFields(): FieldType[] {
    return Array.from(document.querySelectorAll<FieldType>(FIELD_SELECTOR)).filter(isRelevantField);
}

// Data Extraction Functions
export function getFieldLabel(field: FieldType): string {
    return computeAccessibleName(field).trim() ||field.getAttribute("placeholder") ||field.name||field.id || "";
}

export function getFieldDescription(field: FieldType): string {
    return computeAccessibleDescription(field) || "";
}

export function getFieldOptions(field: FieldType): string[] | undefined {
    if (field instanceof HTMLSelectElement) {
        const options = Array.from(field.options).map(option => option.text.trim());
        return options;
    }

    return [];
}

export function extractFieldData(field: FieldType, index: number): DetectedField {
    return {
        fieldID: field.id || `field-${index}`,
        fieldType: field.tagName.toLowerCase(),
        label: getFieldLabel(field),
        description: getFieldDescription(field),
        name: field.name || "",
        placeholder: field.getAttribute("placeholder") || "",
        inputType: field instanceof HTMLInputElement ? field.type : field.tagName.toLowerCase(),
        required: field.required || field.getAttribute("aria-required") === "true",
        options: getFieldOptions(field)
    }
}

// Main Function to Scan Form Fields
export function scanFormFields(): DetectedField[] {
    const fields = detectFormFields();
    return fields.map((field, index) => extractFieldData(field, index));
}

// Helper Functions
function isRelevantField(field: FieldType): boolean {
    // Filter out fields that are not relevant for data collection
    const irrelevantTypes = ["hidden", "submit", "reset", "button", "image"];
    if (isHidden(field) || field.matches(":disabled")) {
        return false;
    }
    if (field instanceof HTMLInputElement && irrelevantTypes.includes(field.type)) {
        return false;
    }
    return true;
}

function isHidden(field: FieldType): boolean {

    if (field instanceof HTMLInputElement && field.type === "hidden") {
        return true;
    }

    // loop through the element and check for hidden attributes or styles
    let element: Element | null = field;
    while (element !== null) {
        if (element.hasAttribute("hidden")) {
            return true;
        }
        if (element.getAttribute("aria-hidden") === "true") {
            return true;
        }
        if (element.hasAttribute("inert")) {
            return true;
        }

        // CSS-based visibility checks
        const style = window.getComputedStyle(element);

        if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") {
            return true;
        }
        element = element.parentElement;
    }

    return false;
}
