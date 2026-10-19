// reads sample from computer
// passes its contents through the extractPDFText() funct
// Printss extracted resume text for inspection
// manual test script

//npx tsx testResume.ts

import { readFile } from "node:fs/promises";
import { extractPDFText } from "./pdfParser.js";

// Read the sample PDF from the fixtures folder
const buffer = await readFile("./fixtures/multipage-resume.pdf");

// Adapt the file for our parser's input interface
const file = {
  size: buffer.length,
  arrayBuffer: async () =>
    Uint8Array.from(buffer).buffer
};

try {
  const pages = await extractPDFText(file);

  for (const page of pages) {
    console.log(`\n--- PAGE ${page.pageNumber} ---`);

    for (const line of page.lines) {
      console.log(line);
    }
  }
} catch (error) {
  console.error("PDF extraction failed:", error instanceof Error ? error.message : String(error));
}
