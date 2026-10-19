//autoamted tests for differente type of error checkings
//calls main function from pdfParser.js
//works with vitest

import { describe, it, expect } from "vitest";
import { readFile } from "node:fs/promises";
import { extractPDFText } from "./pdfParser.js";

describe("PDF Parser", () => {

    // TEST 1: empty file
    it("rejects an empty file", async () => {
        const emptyFile = { size: 0 };

        await expect(
        extractPDFText(emptyFile)
        ).rejects.toThrow("Please select a non-empty PDF.");
    });

    // TEST 2: 
    // checks for mmissing files
    it("rejects a missing file", async () => {
        await expect(
        extractPDFText(null)
        ).rejects.toThrow("Please select a non-empty PDF.");
    });

    // TEST 3: 
    // teal PDF extraction
    it("extracts text from a real resume PDF", async () => {
        const buffer = await readFile(
        "./fixtures/alex.pdf"
        );

        const file = {
        size: buffer.length,
        arrayBuffer: async () =>
            Uint8Array.from(buffer).buffer
        };

        const pages = await extractPDFText(file);

        expect(pages.length).toBeGreaterThan(0);

        const allText = pages
        .flatMap(page => page.lines)
        .join("\n");

        expect(allText).toContain("EDUCATION");
        expect(allText).toContain("EXPERIENCE");
        expect(allText).toContain("PROJECTS");
        expect(allText).toContain("SKILLS");
    });

    // TEST 4: 
    // checks multiple-page PDFs
    it("extracts text from multiple pages", async () => {
        const buffer = await readFile(
        "./fixtures/multipage-resume.pdf"
        );

        const file = {
        size: buffer.length,
        arrayBuffer: async () =>
            Uint8Array.from(buffer).buffer
        };

        const pages = await extractPDFText(file);

        //check that at least two pages were extracted
        expect(pages.length).toBeGreaterThan(1);

        // Check page numbering
        expect(pages[0].pageNumber).toBe(1);
        expect(pages[1].pageNumber).toBe(2);

        //check both pages contain actual text
        expect(
        pages[0].lines.join("").trim().length
        ).toBeGreaterThan(0);

        expect(
        pages[1].lines.join("").trim().length
        ).toBeGreaterThan(0);
    });

    // TEST 5
    // checks for corrupted pdf file
    it("rejects a corrupted PDF", async () => {
    const corruptedData = new TextEncoder().encode(
        "This is not a real PDF file."
    );

    // create a fake uploaded file
    const file = {
        size: corruptedData.length,
        arrayBuffer: async () => corruptedData.buffer
    };

    // corrupted PDF should cause an error
    await expect(
    extractPDFText(file)
    ).rejects.toThrow(
    "This PDF appears to be damaged or invalid.");
    });

    //TEST 6
    // protected pdfs
    it("rejects password-protected PDFs", async () => {
    const buffer = await readFile(
        "./fixtures/protected-resume.pdf"
    );

    const file = {
        size: buffer.length,
        arrayBuffer: async () =>
        Uint8Array.from(buffer).buffer
    };

    await expect(
        extractPDFText(file)
    ).rejects.toThrow(
        "This PDF is password-protected. Please upload an unlocked PDF."
    );
    });

    // TEST 6:
    // checks for pdfs with images
    // no text
    it("rejects image-only PDFs that require OCR", async () => {
    const buffer = await readFile(
        "./fixtures/scanned-resume.pdf"
    );

    const file = {
        size: buffer.length,
        arrayBuffer: async () =>
        Uint8Array.from(buffer).buffer
    };

    await expect(
        extractPDFText(file)
    ).rejects.toThrow(
        "This PDF contains no extractable text."
    );
    });


});
