# CloudClub Fall 2027 — Matchob

Welcome to the club-wide Cloud Club project! 👋

This repo is shared by everyone in the club, so whether this is your first time using Git or your hundredth, you're in the right place. Follow the workflow below to contribute your work without stepping on anyone else's toes. If you get stuck, ask in the club chat or at the next meeting. Everyone was new to this once.

## Ground rules

- **Never push directly to `main`.** All changes go through a pull request (PR).
- **One branch per task.** Keep branches small and focused.
- **Pull often.** Keep your local `main` up to date so you're building on the latest code.

## Git workflow

### 1. Clone the repo (one time only)

Download the project to your computer:

```bash
git clone https://github.com/FSU-CloudClub/CloudClub-Fall2027-Matchob.git
cd CloudClub-Fall2027-Matchob
```

### 2. Create a branch

Always start from an up-to-date `main`, then make a new branch for your task:

```bash
git checkout main
git pull origin main
git checkout -b your-name/short-description
```

Example: `git checkout -b alex/add-login-page`

### 3. Develop

Write your code, test it, and save your files. Check what you've changed at any time with:

```bash
git status
git diff
```

### 4. Stage your changes

Pick which changes go into your next commit:

```bash
git add path/to/file        # stage a specific file
git add .                   # or stage everything in the current directory
```

### 5. Commit

Save a snapshot of your staged changes with a clear message:

```bash
git commit -m "Add login page layout"
```

Write messages that say *what* the change does, e.g. "Fix navbar overflow on mobile", not "stuff" or "updates".

### 6. Push

Upload your branch to GitHub:

```bash
git push -u origin your-name/short-description
```

After the first push, a plain `git push` is enough for that branch.

### 7. Open a pull request

1. Go to the repo on GitHub: https://github.com/FSU-CloudClub/CloudClub-Fall2027-Matchob
2. Click **Compare & pull request** on the banner for your branch (or go to **Pull requests → New pull request**).
3. Set the base to `main` and the compare branch to your branch.
4. Give it a clear title and describe what you changed and how to test it.
5. Request a review, address any feedback, and a maintainer will merge it.

Or, if you have the [GitHub CLI](https://cli.github.com/) installed:

```bash
gh pr create --base main --fill
```

## Quick reference

```bash
git clone https://github.com/FSU-CloudClub/CloudClub-Fall2027-Matchob.git   # once
git checkout main && git pull origin main                                  # sync
git checkout -b your-name/short-description                                # branch
# ...develop...
git add .                                                                  # stage
git commit -m "Describe your change"                                       # commit
git push -u origin your-name/short-description                             # push
# open a PR on GitHub                                                      # pr
```

Happy building! ☁️
