import { describe, it, expect, vi } from "vitest";
import { validateFile, getPresignedURL, uploadPdf, handleResumeUpload } from "./upload_s3.js";
import { readFileSync } from "node:fs";
import { join } from "node:path";
describe("validateFile()", () => {
    it("accepts a valid PDF", () => {
        const file = new File(["PDF content"], "resume.pdf",{ 
            type: "application/pdf" 
        });
        expect(() => validateFile(file)).not.toThrow();
    });

    it("rejects non-PDF files", () => { const file = new File(["text content"], "resume.txt",{ 
        type: "text/plain" 
    });

    expect(() => validateFile(file)).toThrow("Only PDF files allowed!");
    });

    it("rejects empty PDFs", () => {const file = new File([], "empty.pdf",{ 
        type: "application/pdf" 
    });

    expect(() => validateFile(file)).toThrow("File is empty");
    });
});
describe("getPresignedURL()", () => {
    it("successfully retrieves a presigned URL", async () => {
        const file = new File(
            ["PDF content"],
            "resume.pdf",
            { type: "application/pdf" }
        );

        const mockResponse = {
            uploadUrl: "https://example.com/upload",
            resumeId: "resume-123"
        };

        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => mockResponse
        });

        vi.stubGlobal("fetch", fetchMock);

        try {
            const result = await getPresignedURL(file, {
                apiBaseURL: "http://localhost:3001",
                localUserId: "12345"
            });

            expect(result).toEqual(mockResponse);

            expect(fetchMock).toHaveBeenCalledWith(
                "http://localhost:3001/resumes/upload-url",
                expect.objectContaining({
                    method: "POST",
                    headers: expect.objectContaining({
                        "Content-Type": "application/json",
                        "X-Local-User": "12345"
                    })
                })
            );
        } finally {
            vi.unstubAllGlobals();
        }
    });
});
describe("uploadPdf()", () => {
    it("successfully uploads a PDF using PUT", async () => {
        const file = new File(
            ["PDF content"],
            "resume.pdf",
            { type: "application/pdf" }
        );

        const presignedURL = "https://example.com/upload";

        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            status: 200
        });

        vi.stubGlobal("fetch", fetchMock);

        try {
            await uploadPdf(file, presignedURL);

            expect(fetchMock).toHaveBeenCalledWith(
                presignedURL,
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/pdf"
                    },
                    body: file
                }
            );
        } finally {
            vi.unstubAllGlobals();
        }
    });
});
it("throws an error when S3 upload fails", async () => {
    const file = new File(
        ["PDF content"],
        "resume.pdf",
        { type: "application/pdf" }
    );

    const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 403
    });

    vi.stubGlobal("fetch", fetchMock);

    try {
        await expect(
            uploadPdf(file, "https://example.com/upload")
        ).rejects.toThrow("Failed to upload PDF: 403");
    } finally {
        vi.unstubAllGlobals();
    }
});

describe("handleResumeUpload()", () => {
    it("successfully uploads a real PDF resume", async () => {
        // Load an actual PDF from the fixtures directory
        const buffer = readFileSync(
            join(process.cwd(), "fixtures", "alex.pdf")
        );

        const file = new File(
            [new Uint8Array(buffer)],
            "alex.pdf",
            { type: "application/pdf" }
        );

        // Mock backend and S3 responses
        const fetchMock = vi.fn()
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    uploadUrl: "https://example.com/upload",
                    resumeId: "resume-123"
                })
            })
            .mockResolvedValueOnce({
                ok: true,
                status: 200
            });

        vi.stubGlobal("fetch", fetchMock);

        try {
            const result = await handleResumeUpload(file, {
                apiBaseURL: "http://localhost:3001",
                localUserId: "12345"
            });

            expect(result).toEqual({
                key: "resume-123",
                contentType: "application/pdf"
            });

            expect(fetchMock).toHaveBeenCalledTimes(2);

            // First request: Get presigned URL
            expect(fetchMock).toHaveBeenNthCalledWith(
                1,
                "http://localhost:3001/resumes/upload-url",
                expect.objectContaining({
                    method: "POST"
                })
            );

            // Second request: Upload PDF
            expect(fetchMock).toHaveBeenNthCalledWith(
                2,
                "https://example.com/upload",
                expect.objectContaining({
                    method: "PUT",
                    body: file
                })
            );
        } finally {
            vi.unstubAllGlobals();
        }
    });
});