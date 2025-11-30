
import firebase_admin
from firebase_admin import credentials, auth
import os
import sys

# Add web directory to path to find firebase_db if needed, 
# but here we just want to test the key directly first.
sys.path.append(os.path.join(os.getcwd(), 'web'))

KEY_PATH = 'web/serviceAccountKey.json'

def verify_firebase_setup():
    print(f"Checking for key at: {KEY_PATH}")
    if not os.path.exists(KEY_PATH):
        print("ERROR: serviceAccountKey.json not found!")
        return False

    try:
        cred = credentials.Certificate(KEY_PATH)
        # Try initializing (or get existing app)
        try:
            app = firebase_admin.get_app()
        except ValueError:
            app = firebase_admin.initialize_app(cred)
        
        print("SUCCESS: Firebase Admin SDK initialized successfully.")
        
        # Optional: Try to list users (requires Auth to be enabled)
        print("Attempting to list users (tests Auth permission)...")
        try:
            page = auth.list_users(max_results=5)
            print(f"SUCCESS: Successfully connected to Auth. Found {len(page.users)} users.")
        except Exception as e:
            print(f"WARNING: Could not list users. This might be because Auth is not enabled in Console yet, or the key has insufficient permissions.\nError: {e}")
            
        return True
    except Exception as e:
        print(f"ERROR: Failed to initialize Firebase: {e}")
        return False

if __name__ == "__main__":
    verify_firebase_setup()
