
export interface UploadResult {
    key: string;
    contentType: string;
}

export interface PresignedUpload {
    uploadUrl: string;
    resumeId: string;
}

export interface UploadConfig {
    apiBaseURL: string;
    accessToken?: string;
    localUserId?: string;
}

export function validateFile(file: File): void {
    const maxSize = 5 * 1024 * 1024; // 5 MB maximum

    if (file.type !== "application/pdf") {
        throw new Error("Only PDF files allowed!");
    }

    if (file.size === 0) {
        throw new Error("File is empty");
    }

    if (file.size > maxSize){
        throw new Error("PDF exceeds the 5 MB limit");
    }

}

// Request a presigned S3 upload URL from the backend
export async function getPresignedURL(file: File, config: UploadConfig): Promise<PresignedUpload> {

    const headers: Record<string, string> = {
        "Content-Type": "application/json"
    };
    const isLocal = new URL(config.apiBaseURL).hostname === "localhost";

    if (isLocal && config.localUserId) {
        // Local development authentication
        headers["X-Local-User"] = config.localUserId;
    } 
    else if (config.accessToken) {
        // AWS Cognito authentication
        headers["Authorization"] = `Bearer ${config.accessToken}`;
    } 
    else {
        throw new Error("Authentication is required");
    }

    const baseURL = config.apiBaseURL.replace(/\/+$/, "");
    const response = await fetch(`${baseURL}/resumes/upload-url`,{
            method: "POST",
            headers,
            body: JSON.stringify({
                fileName: file.name,
                contentType: "application/pdf"
            })
        }
    );

    if (!response.ok) {
        throw new Error(`Failed to get presigned URL: ${response.status}`);
    }
    const data: PresignedUpload = await response.json();
    return data;
}

// Upload PDF directly to S3 using the presigned URL
export async function uploadPdf(file: File, presignedURL: string): Promise<void> {

    const response = await fetch(presignedURL, {
        method: "PUT",
        headers: {
            "Content-Type": "application/pdf"
        },
        body: file
    });

    if (!response.ok) {
        throw new Error(`Failed to upload PDF: ${response.status}`);
    }
}

// Main upload function
export async function handleResumeUpload(file: File, config: UploadConfig): Promise<UploadResult> {
    validateFile(file);
    const { uploadUrl, resumeId } = await getPresignedURL(file, config);
    await uploadPdf(file, uploadUrl);
    return {
        key: resumeId,
        contentType: "application/pdf"
    };
}