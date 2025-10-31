# 🐳 Update Docker Desktop

## Current Version
- **Docker CLI**: 28.5.1
- **Docker Desktop**: 4.48.0

## Quick Update Methods

### Method 1: In-App Update (Easiest) ⭐

1. **Open Docker Desktop** (if not already open)
   - Look for Docker whale icon in system tray
   - Or Start Menu → Docker Desktop

2. **Go to Settings**
   - Click the **⚙️ gear icon** (top-right)
   - Or right-click system tray icon → Settings

3. **Check for Updates**
   - Click **"General"** tab (left sidebar)
   - Scroll to **"Check for Updates"** section
   - Click **"Check for Updates"** button

4. **Install Update**
   - If update available, click **"Download & Restart"**
   - Docker will download and restart automatically

### Method 2: Download Latest Installer

1. **Download**: Visit https://www.docker.com/products/docker-desktop
2. **Download** Docker Desktop for Windows
3. **Run installer** - it will update your existing installation
4. **Restart** Docker Desktop after installation

### Method 3: Microsoft Store (If installed from Store)

1. Open **Microsoft Store** app
2. Click **"Library"** (bottom-left)
3. Click **"Get updates"** button
4. Wait for Docker Desktop to update

## Verify Update

After updating, check your version:

```powershell
docker --version
```

## After Update

1. **Restart Docker Desktop** (if needed)
2. **Verify it's running**: `docker ps`
3. **Continue with deployment**: `.\deploy-to-cloud-run.ps1`

## Notes

- ✅ You can update Docker Desktop while it's running
- ⚠️ Update may require a restart of Docker Desktop
- 💾 All containers and images are preserved during update
- 🔄 Docker Desktop will restart automatically after update

---

**Quick Command**: Run `.\update-docker.ps1` for interactive update guide

