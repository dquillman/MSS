# ONE Simple Step Left! 🎯

## ✅ What's Already Done (by me):
- ✅ Service account created
- ✅ Permissions set up
- ✅ Key file ready

## 📝 What You Need to Do (5 minutes):

### Step 1: Open GitHub
Go to: **https://github.com/dquillman/MSS/settings/secrets/actions**

### Step 2: Add 3 Secrets

Click "New repository secret" and add these one by one:

**Secret #1:**
- Name: `GCP_PROJECT_ID`
- Value: `mss-tts`
- Click "Add secret"

**Secret #2:**
- Name: `GCP_SA_KEY`
- Value: (open the file `github-actions-key.json` in this folder, copy ALL of it, paste here)
- Click "Add secret"

**Secret #3:**
- Name: `GCP_SERVICE_ACCOUNT_EMAIL`
- Value: `github-actions-deployer@mss-tts.iam.gserviceaccount.com`
- Click "Add secret"

### Step 3: Done!
That's it! GitHub Actions will now work automatically.

---

## 🖼️ Visual Guide:

1. **Open:** https://github.com/dquillman/MSS/settings/secrets/actions
2. **Click:** "New repository secret" (green button)
3. **Fill in:** Name and Value
4. **Click:** "Add secret"
5. **Repeat** for all 3 secrets

---

## 📄 The Key File Location:
The file `github-actions-key.json` is in your MSS folder.
Just open it, copy everything, and paste into the `GCP_SA_KEY` secret.

---

**That's literally it!** Just 3 secrets to add, then you're done! 🎉

