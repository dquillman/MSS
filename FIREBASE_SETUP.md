# Firebase Setup Instructions

The application has been migrated to use Firebase for Authentication and Database.
To complete the setup, please follow these steps:

## 1. Enable Authentication
1. Go to the [Firebase Console](https://console.firebase.google.com/project/mss-video-creator-app/authentication/providers).
2. Click on **Build** > **Authentication**.
3. Click **Get Started** (if not already enabled).
4. Select the **Sign-in method** tab.
5. Click on **Email/Password**.
6. Enable **Email/Password** and click **Save**.

## 2. Get Service Account Key (Backend)
The backend needs a service account key to communicate with Firebase.
1. Go to [Project Settings > Service accounts](https://console.firebase.google.com/project/mss-video-creator-app/settings/serviceaccounts/adminsdk).
2. Click **Generate new private key**.
3. Click **Generate key** to download the JSON file.
4. Rename the downloaded file to `serviceAccountKey.json`.
5. Move the file to the `web/` directory in your project:
   `g:\Users\daveq\MSS\web\serviceAccountKey.json`

## 3. Install Dependencies
Run the following command to install the new dependencies:
```bash
pip install -r requirements.txt
```

## 4. Restart Server
Restart your Flask server to apply the changes.
```bash
python web/api_server.py
```

## 5. Verify
1. Open the application in your browser.
2. Go to the Login page.
3. Try to Sign Up with a new account.
4. You should be redirected to the Studio upon success.
