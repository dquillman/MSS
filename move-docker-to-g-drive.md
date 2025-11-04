# Move Docker Desktop WSL Data To G: Drive

## Prerequisites
- Close all running containers/apps
- Quit Docker Desktop completely (right-click tray icon → **Quit Docker Desktop**)
- Open PowerShell as Administrator:
  - Click Start
  - Type `powershell`
  - Right-click "Windows PowerShell"
  - Select "Run as administrator"
  - Click "Yes" when prompted

---

## Step 1 – Create workspace folders on G:

```powershell
New-Item -ItemType Directory -Path 'G:\wsl' -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Path 'G:\wsl\imports' -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Path 'G:\wsl\docker-desktop' -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Path 'G:\wsl\docker-desktop-data' -ErrorAction SilentlyContinue | Out-Null
```

---

## Step 2 – Confirm Docker's WSL distros exist

```powershell
wsl --list --verbose
```

**Expected output:** You should see `docker-desktop` and `docker-desktop-data` both with version 2.

---

## Step 3 – Export the distros to G:

```powershell
wsl --export docker-desktop 'G:\wsl\imports\docker-desktop.tar'
wsl --export docker-desktop-data 'G:\wsl\imports\docker-desktop-data.tar'
```

**Note:** These commands may take several minutes. Wait for both to complete.

---

## Step 4 – Remove the originals from C:

```powershell
wsl --unregister docker-desktop
wsl --unregister docker-desktop-data
```

**Note:** This deletes the old VHDX files on C: but keeps your exports on G: safe.

---

## Step 5 – Import distros onto G:

```powershell
wsl --import docker-desktop 'G:\wsl\docker-desktop' 'G:\wsl\imports\docker-desktop.tar' --version 2
wsl --import docker-desktop-data 'G:\wsl\docker-desktop-data' 'G:\wsl\imports\docker-desktop-data.tar' --version 2
```

**Note:** Each command unpacks the .tar into the new location on G:.

---

## Step 6 – Verify the move

```powershell
wsl --list --verbose
```

**Expected output:** Both `docker-desktop` and `docker-desktop-data` should appear again.

---

## Step 7 – Configure Docker Desktop

1. **Start Docker Desktop** (it may take a minute on first launch)

2. **Open Settings → Resources → Advanced**
   - Set **Disk image location** to `G:\wsl\docker-desktop-data`
   - Click **Browse**, select the folder, then **Apply & Restart**

3. **Open Settings → Resources → WSL Integration**
   - Confirm `docker-desktop` is enabled/checked

4. **Test Docker is working:**

```powershell
docker run hello-world
```

**Expected output:** Should print the hello-world welcome message.

---

## Step 8 – Cleanup (after confirming everything works)

```powershell
Remove-Item 'G:\wsl\imports\docker-desktop.tar','G:\wsl\imports\docker-desktop-data.tar'
```

**Note:** Only delete these backup .tar files once you're 100% sure Docker is working correctly.

---

## Troubleshooting

**If wsl --import fails:**
- Delete the partially created folder and re-run the import command
- Make sure the target folders are empty before importing

**If Docker Desktop won't start:**
- Quit Docker Desktop
- Re-run `wsl --unregister` for both distros
- Re-import from the .tar backups

**To check disk space freed on C::**
```powershell
wsl --list --verbose
Get-ChildItem 'C:\Users\*\AppData\Local\Docker\wsl' -Recurse | Measure-Object -Property Length -Sum
```

---

## Optional: Clean up Docker before export (saves space)

If you want to reduce the size of the export, run this **before Step 3** (while Docker Desktop is still running):

```powershell
docker system prune --all --volumes
```

Type `y` to confirm. This removes unused images, containers, and volumes.

