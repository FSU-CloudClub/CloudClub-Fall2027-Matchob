//MAIN SCRIPT
//PDF PARSING
import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf.mjs";

// Type of file data this parser needs (works with browser File objects too).
export interface PDFFileInput {
  size: number;
  arrayBuffer(): Promise<ArrayBuffer>;
}

// Output structure for each extracted PDF page.
export interface PDFPage {
  pageNumber: number;
  lines: string[];
}

//opens PDFs, extracts text, processes hasEOL, and handles errors.
export async function extractPDFText(file: PDFFileInput | null): Promise<PDFPage[]> {
  if (!file || file.size === 0) {
    throw new Error("Please select a non-empty PDF.");
  }

  let loadingTask: ReturnType<typeof pdfjsLib.getDocument> | undefined;

  try {
    const buffer = await file.arrayBuffer();
    const data = new Uint8Array(buffer);

    loadingTask = pdfjsLib.getDocument({ data });
    const pdf = await loadingTask.promise;

    const pages: PDFPage[] = [];

    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
      const page = await pdf.getPage(pageNumber);
      const content = await page.getTextContent();

      const lines: string[] = [];
      let currentLine = "";

      for (const item of content.items) {
        if (!("str" in item) || typeof item.str !== "string") continue;

        currentLine += item.str;

        if (item.hasEOL) {
          lines.push(currentLine);
          currentLine = "";
        }
      }

      if (currentLine) {
        lines.push(currentLine);
      }

      pages.push({ pageNumber, lines });
    }

    const hasText = pages.some(page =>
      page.lines.some(line => line.trim().length > 0)
    );

    if (!hasText) {
      throw new Error(
        "This PDF contains no extractable text. It may be scanned and require OCR."
      );
    }

    return pages;

  } catch (error: unknown) {
    // TypeScript requires checking an unknown error before reading its properties.
    if (!(error instanceof Error)) {
      throw new Error("Unable to read this PDF. Please try another file.", { cause: error });
    }

    // Preserve our own actionable error
    if (error.message?.includes("no extractable text")) {
      throw error;
    }

    // Handle password-protected PDFs
    if (error.name === "PasswordException") {
      throw new Error(
        "This PDF is password-protected. Please upload an unlocked PDF."
      );
    }

    // Handle malformed or corrupted PDFs
    if (error.name === "InvalidPDFException" ||
        error.name === "MissingPDFException") {
      throw new Error(
        "This PDF appears to be damaged or invalid. Please upload another PDF."
      );
    }

    // Handle other unexpected errors
    throw new Error(
      "Unable to read this PDF. Please try another file.",
      { cause: error }
    );

  } finally {
    if (loadingTask) {
      await loadingTask.destroy();
    }
  }
}
