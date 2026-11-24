# Local resume API

`resumeApi.ts` calls the backend started by `backend/SAMproject/dev.py`.
The default API URL is `http://localhost:3001`; requests send `X-Local-User: 12345`
for the seeded profile. No login is needed. This client intentionally rejects
remote API hosts and is not a production authentication implementation.

Optional overrides in `frontend/.env.local`:

```dotenv
WXT_API_BASE_URL=http://localhost:3001
WXT_LOCAL_USER=12345
```

A different user must already have a profile. Restart WXT after changing settings.
If changing S3's published port, also update backend `S3_PUBLIC_ENDPOINT`.

Start the backend with `python3 dev.py` from `backend/SAMproject`, then run
`npm run dev` from `frontend`. Open Matchob and select Get Started. For a manually
loaded extension, run `npm run build` and reload it at `chrome://extensions`.
The manifest includes localhost host permissions for both the API and S3Mock.

The Vault loads real metadata and supports PDF uploads (up to 5 MB), rename,
tags, delete, preview, and download. Upload requests get a presigned URL, then
PUT bytes to S3 without API auth headers. Failed uploads attempt metadata cleanup.
The backend resets local data on restart. Suggestions and autofill remain separate
mock flows; this integration does not call Bedrock.

Manual verification: upload a PDF, refresh the list, edit its name/tags, download
and compare the file, then delete it and refresh again. Also stop the backend to
verify the error message and retry using Refresh.
