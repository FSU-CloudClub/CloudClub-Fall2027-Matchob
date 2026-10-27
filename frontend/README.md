# Matchob frontend

A small WXT + React + TypeScript browser extension scaffold for the frontend team. The first target is Chrome. The popup previews the planned screens; Sprint 1 feature behavior is intentionally left for assigned teammates.

## Prerequisites

- Node.js 22 or newer (required by the installed WXT version)
- npm
- Google Chrome for the local extension preview

## Install and run

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

WXT opens Chrome with the extension loaded. Click the Matchob extension icon to open the popup. `Get Started`, `Back`, and `Next` navigate the preview screens. The Resume Vault includes a PDF picker and drag-and-drop upload preview; uploads appear while the Vault screen stays open but are not saved to a backend. On Windows PowerShell, use `npm.cmd` in place of `npm` if script execution is disabled.

## Load and test in Chrome

For a manual check without the development runner:

1. Run `npm run build` from `frontend/`.
2. Open `chrome://extensions` in Chrome and turn on **Developer mode**.
3. Click **Load unpacked** and select `frontend/.output/chrome-mv3/`.
4. Pin Matchob from Chrome's extensions menu, then click its icon. Click **Get Started** to see the Resume Vault and upload preview.

After rebuilding, click **Reload** on the Matchob card in `chrome://extensions` to see the new build.

To check types and create a production build:

```bash
npm run check
npm run build
```

The build is written to `.output/chrome-mv3/`. Generated and local folders (`.output/`, `.wxt/`, `.npm-cache/`, and `node_modules/`) are ignored by Git and should not be committed. Commit `package-lock.json` so teammates get the same dependency versions.

## Where to work

- `entrypoints/popup/` is the WXT popup entrypoint. WXT discovers its `index.html` automatically.
- `pages/` contains placeholder screens for later workflow steps.
- `features/resumes/` contains task-specific placeholders for the Vault, upload, tags and rename, delete, and preview and download work.
- `components/` contains reusable UI elements.
- `types/` defines shared frontend data shapes.
- `mocks/` contains sample resume and recommendation data.
- `services/` defines the resume API contract and explicit mutation stubs.
- `utils/` contains shared, frontend-only helpers.

Chrome is the only target scripted for now. WXT supports separate browser builds, so a future Safari target can be added without changing the popup's React components. Browser-specific APIs should stay out of shared components.

## Sprint 1 ownership map

| Task | Starting point |
| --- | --- |
| Frontend Layout + Nav | `entrypoints/popup/App.tsx` and `style.css` |
| Resume Vault UI | `features/resumes/ResumeVault.tsx` |
| Resume Upload Component | `features/resumes/ResumeUpload.tsx` |
| Extension Autofill UI | `pages/AutoFillReviewScreen.tsx` |
| Resume Tags + Rename UI | `features/resumes/ResumeTagsRename.tsx` |
| Resume Delete Flow | `features/resumes/ResumeDeleteDialog.tsx` |
| Resume Preview + Download UI | `features/resumes/ResumePreviewDownload.tsx` |
| S3 Presigned Upload Integration | `services/resumeApi.ts` and backend contract |
| Resume Parsing Integration | Add a parsing service after its API contract is agreed |
| Autofill Script Integration | Add a WXT content script when the interaction contract is agreed |

The popup has only local preview navigation. No background or content script is registered yet, and no live backend requests are made.
