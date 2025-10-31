# How to Delete Multiple Failed GitHub Actions Runs

## Method 1: GitHub CLI (Recommended for Bulk Deletion)

### Install GitHub CLI (if not installed)

**Windows (PowerShell):**
```powershell
winget install --id GitHub.cli
```

**Mac:**
```bash
brew install gh
```

**Linux:**
```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh
```

### Authenticate
```bash
gh auth login
```

### Delete Failed Runs

**Delete all failed runs for a specific workflow:**
```bash
# Replace YOUR_USERNAME and REPO_NAME with your values
# Replace workflow-name with your workflow (e.g., "Build and Deploy to Google Cloud Run")
gh run list --workflow="Build and Deploy to Google Cloud Run" --status failure --limit 1000 | \
  awk '{print $7}' | \
  xargs -I {} gh run delete {}
```

**Delete all failed runs (all workflows):**
```bash
gh run list --status failure --limit 1000 | \
  awk '{print $7}' | \
  xargs -I {} gh run delete {}
```

**Interactive deletion (safer - asks for confirmation):**
```bash
gh run list --status failure --limit 1000 --json databaseId --jq '.[].databaseId' | \
  xargs -I {} gh run delete {} --confirm
```

### PowerShell Version (Windows)

```powershell
# Delete all failed runs for a specific workflow
gh run list --workflow "Build and Deploy to Google Cloud Run" --status failure --limit 1000 --json databaseId --jq '.[].databaseId' | ForEach-Object {
    gh run delete $_ --confirm
}

# Delete all failed runs (all workflows)
gh run list --status failure --limit 1000 --json databaseId --jq '.[].databaseId' | ForEach-Object {
    gh run delete $_ --confirm
}
```

---

## Method 2: GitHub Web UI (Manual, One by One)

1. Go to your repository: `https://github.com/YOUR_USERNAME/MSS`
2. Click **Actions** tab
3. Click on the workflow name (e.g., "Build and Deploy to Google Cloud Run")
4. For each failed run:
   - Click on the run
   - Click the **"..."** menu (three dots) in the top right
   - Select **"Delete run"**
   - Confirm deletion

**Note:** This is slow for many runs, but safe if you want to review each one.

---

## Method 3: GitHub Web UI (Bulk - Limited)

GitHub doesn't support selecting multiple runs for bulk deletion in the UI. You can only:
- Filter runs by status (success, failure, etc.)
- Delete them one by one

If you have many runs, use Method 1 (CLI) instead.

---

## Method 4: GitHub API (Advanced)

**Get all failed run IDs:**
```bash
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
  "https://api.github.com/repos/YOUR_USERNAME/MSS/actions/runs?status=failure&per_page=100" | \
  jq -r '.workflow_runs[].id'
```

**Delete each run:**
```bash
# Replace RUN_ID with actual ID
curl -X DELETE \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  "https://api.github.com/repos/YOUR_USERNAME/MSS/actions/runs/RUN_ID"
```

**Script to delete all:**
```bash
# Get token from: https://github.com/settings/tokens (need 'repo' scope)
GITHUB_TOKEN="your_token_here"
REPO="YOUR_USERNAME/MSS"

# Get all failed run IDs and delete them
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$REPO/actions/runs?status=failure&per_page=100" | \
  jq -r '.workflow_runs[].id' | \
  while read run_id; do
    echo "Deleting run $run_id..."
    curl -X DELETE \
      -H "Authorization: token $GITHUB_TOKEN" \
      "https://api.github.com/repos/$REPO/actions/runs/$run_id"
    sleep 0.5  # Rate limit protection
  done
```

---

## Quick PowerShell Script for Windows

Create `delete-failed-runs.ps1`:

```powershell
# Authenticate first: gh auth login

$workflow = "Build and Deploy to Google Cloud Run"
$status = "failure"
$limit = 1000

Write-Host "Fetching failed runs for workflow: $workflow" -ForegroundColor Yellow

$runs = gh run list --workflow $workflow --status $status --limit $limit --json databaseId,status,conclusion,createdAt

if ($runs) {
    $runIds = $runs | ConvertFrom-Json | ForEach-Object { $_.databaseId }
    $count = $runIds.Count
    
    Write-Host "Found $count failed runs" -ForegroundColor Cyan
    $confirm = Read-Host "Delete all $count failed runs? (yes/no)"
    
    if ($confirm -eq "yes") {
        foreach ($id in $runIds) {
            Write-Host "Deleting run $id..." -ForegroundColor Gray
            gh run delete $id --confirm
        }
        Write-Host "Done! Deleted $count runs." -ForegroundColor Green
    } else {
        Write-Host "Cancelled." -ForegroundColor Yellow
    }
} else {
    Write-Host "No failed runs found." -ForegroundColor Green
}
```

Run it:
```powershell
.\delete-failed-runs.ps1
```

---

## Tips

1. **Keep Recent Runs:** Only delete old failed runs. Recent ones might be useful for debugging.

2. **Rate Limits:** GitHub API has rate limits (5000 requests/hour). If you have thousands of runs, add delays between deletions.

3. **Workflow-Specific:** Use `--workflow` flag to only delete runs from specific workflows.

4. **Status Filters:** You can filter by:
   - `--status failure` (failed runs)
   - `--status cancelled` (cancelled runs)
   - `--status success` (successful runs - use carefully!)

5. **Dry Run:** Test with `--limit 5` first to see what would be deleted.

---

## Example: Delete All Failed Runs from Last 30 Days

```bash
# Get failed runs created in last 30 days
gh run list --status failure --limit 1000 --json databaseId,createdAt --jq '.[] | select(.createdAt < (now - 30*24*3600 | strftime("%Y-%m-%dT%H:%M:%SZ"))) | .databaseId' | \
  xargs -I {} gh run delete {} --confirm
```

---

## Verification

After deletion, verify:
```bash
# Count remaining failed runs
gh run list --status failure --limit 1000 | wc -l
```

---

## Need Help?

- GitHub CLI docs: https://cli.github.com/manual/gh_run
- GitHub API docs: https://docs.github.com/en/rest/actions/runs

