# How to Use the Service Account JSON Key

## Finding the File

When you download the JSON key from Google Cloud Console:
- **Location:** Usually in your **Downloads** folder
- **Filename:** Something like `mss-tts-XXXXX.json` or similar
- **Extension:** `.json`

**The filename doesn't matter** - only the **content** inside matters!

---

## Step-by-Step: Copy JSON Content

### Method 1: Using Notepad (Windows)

1. **Find the file:**
   - Check your Downloads folder
   - Look for a `.json` file you just downloaded

2. **Open it:**
   - Right-click the file
   - Select **"Open with"** → **"Notepad"**

3. **Copy everything:**
   - Press **Ctrl+A** (Select All)
   - Press **Ctrl+C** (Copy)

4. **Paste into GitHub:**
   - Go to GitHub → Settings → Secrets
   - Click **"New repository secret"**
   - Name: `GCP_SA_KEY`
   - Paste (Ctrl+V) the entire JSON
   - Click **"Add secret"**

---

### Method 2: Using VS Code or Any Text Editor

1. **Open the file** in your text editor
2. **Select All** (Ctrl+A)
3. **Copy** (Ctrl+C)
4. **Paste into GitHub secret**

---

## What the JSON Looks Like

The file should start like this:
```json
{
  "type": "service_account",
  "project_id": "mss-tts",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "mss-tts@mss-tts.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  ...
}
```

**Make sure you copy the ENTIRE file** - from the opening `{` to the closing `}`!

---

## Important Notes

1. **The filename doesn't matter** - GitHub doesn't care what the file was named
2. **Copy the entire JSON** - Don't miss any part of it
3. **One continuous block** - Should be one big JSON object (starts with `{` and ends with `}`)
4. **No extra spaces** - The JSON content itself is fine (GitHub handles it)

---

## Troubleshooting

### "Invalid JSON" error in GitHub
- Make sure you copied the ENTIRE file
- Check that it starts with `{` and ends with `}`
- Make sure you didn't accidentally copy just part of it

### "Can't find the file"
- Check your Downloads folder
- Look for `.json` files sorted by date (most recent)
- The file was downloaded when you clicked "CREATE" on the key

### "File looks wrong"
- Should be one continuous JSON block
- Should contain `"type": "service_account"`
- Should contain `"client_email": "mss-tts@mss-tts.iam.gserviceaccount.com"`

---

## Quick Checklist

- [ ] Downloaded JSON key from Service Accounts → KEYS tab
- [ ] Found the `.json` file in Downloads (or wherever it saved)
- [ ] Opened the file in text editor
- [ ] Selected ALL content (Ctrl+A)
- [ ] Copied it (Ctrl+C)
- [ ] Went to GitHub → Settings → Secrets → Actions
- [ ] Created new secret: `GCP_SA_KEY`
- [ ] Pasted the entire JSON content
- [ ] Saved the secret

---

That's it! The filename is just for your reference - GitHub only needs the JSON content inside.


