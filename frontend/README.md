# Matchob frontend

A small WXT + React + TypeScript browser extension scaffold. The first target is Chrome. The popup previews the planned MVP screens with local navigation and sample recommendation data; uploads, AI calls, auto-fill, and authentication are not implemented.

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

WXT opens Chrome with the extension loaded. Click the Matchob extension icon to open the popup. `Get Started`, `Back`, and `Next` let you preview the placeholder screens. On Windows PowerShell, use `npm.cmd` in place of `npm` if script execution is disabled.

## Load and test in Chrome

For a manual check without the development runner:

1. Run `npm run build` from `frontend/`.
2. Open `chrome://extensions` in Chrome and turn on **Developer mode**.
3. Click **Load unpacked** and select `frontend/.output/chrome-mv3/`.
4. Pin Matchob from Chrome's extensions menu, then click its icon. The popup should show **Matchob**, **AI-powered resume tailoring**, and **Get Started**. Click the button to preview the next screen.

After rebuilding, click **Reload** on the Matchob card in `chrome://extensions` to see the new build.

To check types and create a production build:

```bash
npm run check
npm run build
```

The build is written to `.output/chrome-mv3/`. Generated and local folders (`.output/`, `.wxt/`, `.npm-cache/`, and `node_modules/`) are ignored by Git and should not be committed. Commit `package-lock.json` so teammates get the same dependency versions.

## Where to work

- `entrypoints/popup/` is the WXT popup entrypoint. WXT discovers its `index.html` automatically.
- `pages/` contains one small component per MVP screen.
- `components/` contains reusable UI elements.
- `types/` defines starter data shapes.
- `mocks/` contains local sample data.
- `services/` is reserved for future backend requests.
- `utils/` contains shared, frontend-only helpers.

Chrome is the only target scripted for now. WXT supports separate browser builds, so a future Safari target can be added without changing the popup's React components. Browser-specific APIs should stay out of shared components.
