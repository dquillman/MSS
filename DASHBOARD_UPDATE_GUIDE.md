# How to Update the Dashboard

## ⚠️ Important: Dashboard Uses JSON, Not Markdown!

The dashboard **cannot** load `.md` files. It needs a **JSON file** with this format:

```json
[
  {"agent": "1", "phase": "1", "task": "1"},
  {"agent": "1", "phase": "1", "task": "2"},
  {"agent": "3", "phase": "1", "task": "1"}
]
```

---

## ✅ Solution: Use the JSON File

I've created `agent-progress.json` with your current progress. Here's how to use it:

### Option 1: Load the JSON File (Recommended)

1. **Open the dashboard:**
   ```
   web/topic-picker-standalone/agent-dashboard.html
   ```

2. **Click "Load Progress" button**

3. **Select the JSON file:**
   - Choose `agent-progress.json` (in project root)
   - NOT `AGENT_PROGRESS.md` ❌

4. **Done!** Progress should update automatically

### Option 2: Export Current Progress

1. **Open dashboard**
2. **Check off tasks** you've completed
3. **Click "Export Progress"** button
4. **Save the JSON file** (you can reload it later)

### Option 3: Check Tasks Directly in Dashboard

1. **Open dashboard**
2. **Manually check off** completed tasks
3. **Progress saves automatically** to browser localStorage

---

## 📁 File Locations

**Dashboard:** `web/topic-picker-standalone/agent-dashboard.html`  
**JSON Progress File:** `agent-progress.json` (root directory)  
**Markdown Progress:** `AGENT_PROGRESS.md` (for reading, not loading)

---

## 🔧 Quick Fix

The dashboard now has better error messages. If you try to load a markdown file, it will tell you exactly what format it expects.

---

## 💡 Pro Tip

**Best Workflow:**
1. Work on tasks
2. Check them off in dashboard (saves automatically)
3. Export JSON when done (backup)
4. Load JSON next time you open dashboard

**The dashboard tracks progress in your browser**, so it persists between sessions on the same browser!

