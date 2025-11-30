# How to Get Your Firebase Service Account Key

I cannot generate this key for you because it requires logging into your private Google/Firebase account. However, here are the **exact, slow steps** to do it yourself.

## Step 1: Open the Firebase Console
1.  Open your web browser.
2.  Click this link to go directly to the Service Accounts page for your project:
    [**https://console.firebase.google.com/project/mss-video-creator-app/settings/serviceaccounts/adminsdk**](https://console.firebase.google.com/project/mss-video-creator-app/settings/serviceaccounts/adminsdk)
    *(If you are not logged in, you will need to log in with your Google account first).*

## Step 2: Generate the Key
1.  Look for a blue button that says **"Generate new private key"**. It is usually at the bottom of the page.
2.  Click that button.
3.  A warning window will pop up. Click the **"Generate key"** button in that window.
4.  A file will automatically download to your computer.
    *   The filename will look something like: `mss-video-creator-app-firebase-adminsdk-xxxxx-yyyyyy.json`

## Step 3: Rename and Move the File
1.  Go to your **Downloads** folder (or wherever the file was saved).
2.  **Rename** the file to exactly:
    `serviceAccountKey.json`
    *(Make sure it doesn't have `.json` twice, like `serviceAccountKey.json.json`)*.
3.  **Copy** or **Cut** this file.
4.  **Paste** it into this specific folder in your project:
    `g:\Users\daveq\MSS\web\`

## Step 4: Verify
1.  Once you have pasted the file, tell me "I have added the key".
2.  I will then check if it is in the right place and verify everything is working.
