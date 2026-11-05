# GitHub Profile README Setup — @nawsintabassum

This package is prepared for the profile repository **nawsintabassum/nawsintabassum**. It keeps the dark Tokyo Night-style cards and includes GitHub statistics, activity, contribution streak, contribution snake, and a visible GitHub Trophies section.

## Publish the profile

1. Open or create the public repository named exactly `nawsintabassum` under the `nawsintabassum` GitHub account.
2. Upload the contents of this folder to the repository root (not the folder itself). The `README.md` must be at the root.
3. Commit the files to the `main` branch.
4. Open **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions**. Save.
5. Open **Actions → Update GitHub Profile Cards → Run workflow** and run it once.
6. Open **Actions → Generate Contribution Snake → Run workflow** and run it once.

The workflows refresh the self-hosted statistics/activity SVGs daily and refresh the contribution snake every six hours. The trophy image is rendered from the GitHub Profile Trophy service and uses the correct username.

## Notes

- The workflows use the repository's built-in `GITHUB_TOKEN`; no personal access token needs to be added.
- If GitHub Actions is disabled for the repository, enable it under **Settings → Actions → General**.
- The statistics cards appear after the first successful workflow run.
- GitHub Trophies are a separate external image, so they may take a moment to load.
