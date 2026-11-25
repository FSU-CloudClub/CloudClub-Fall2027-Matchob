import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { uploadResume } from "../frontend/services/uploadResume.js";
const PDF_TYPE = "application/pdf";
const DOCX_TYPE =
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

describe("uploadResume()", () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });
    afterEach(() => {
        vi.useRealTimers();
    });
    it("successfully uploads a PDF resume", async () => {
        const file = new File(
            ["PDF content"],
            "resume.pdf",
            { type: PDF_TYPE }
        );

        const promise = uploadResume(file, PDF_TYPE);

        await vi.advanceTimersByTimeAsync(1500);

        const result = await promise;

        expect(result.contentType).toBe(PDF_TYPE);
        expect(result.key).toMatch(/^mock\/resumes\/.+\.pdf$/);
    });

    it("successfully uploads a DOCX resume", async () => {
        const file = new File(
            ["DOCX content"],
            "resume.docx",
            { type: DOCX_TYPE }
        );

        const promise = uploadResume(file, DOCX_TYPE);

        await vi.advanceTimersByTimeAsync(1500);

        const result = await promise;

        expect(result.contentType).toBe(DOCX_TYPE);
        expect(result.key).toMatch(/^mock\/resumes\/.+\.docx$/);
    });

    it("throws an error when the upload fails", async () => {
        const file = new File(
            ["PDF content"],
            "fail-resume.pdf",
            { type: PDF_TYPE }
        );

        const promise = uploadResume(file, PDF_TYPE);

        const assertion = expect(promise)
            .rejects.toThrow("Mock upload failure");

        await vi.advanceTimersByTimeAsync(1500);

        await assertion;
    });

    it("handles failure filenames regardless of capitalization", async () => {
        const file = new File(
            ["PDF content"],
            "FAIL-resume.pdf",
            { type: PDF_TYPE }
        );

        const promise = uploadResume(file, PDF_TYPE);

        const assertion = expect(promise)
            .rejects.toThrow("Mock upload failure");

        await vi.advanceTimersByTimeAsync(1500);

        await assertion;
    });

    it("generates unique keys for separate uploads", async () => {
        const file = new File(
            ["PDF content"],
            "resume.pdf",
            { type: PDF_TYPE }
        );

        const firstUpload = uploadResume(file, PDF_TYPE);
        const secondUpload = uploadResume(file, PDF_TYPE);

        await vi.advanceTimersByTimeAsync(1500);

        const result1 = await firstUpload;
        const result2 = await secondUpload;

        expect(result1.key).not.toBe(result2.key);
    });

    it("uses the canonical content type from validation", async () => {
        const file = new File(
            ["PDF content"],
            "resume.pdf",
            { type: "" }
        );

        const promise = uploadResume(file, PDF_TYPE);

        await vi.advanceTimersByTimeAsync(1500);

        const result = await promise;

        expect(result.contentType).toBe(PDF_TYPE);
        expect(result.key).toMatch(/\.pdf$/);
    });

    it("successfully uploads a real PDF fixture", async () => {
        const { readFileSync } = await import("node:fs");
        const { join } = await import("node:path");

        const buffer = readFileSync(
                new URL("./fixtures/alex.pdf", import.meta.url)
        );
        const file = new File(
            [new Uint8Array(buffer)],
            "alex.pdf",
            { type: PDF_TYPE }
        );

        const promise = uploadResume(file, PDF_TYPE);

        await vi.advanceTimersByTimeAsync(1500);

        const result = await promise;

        expect(result.contentType).toBe(PDF_TYPE);
        expect(result.key).toMatch(/^mock\/resumes\/.+\.pdf$/);
    });
});