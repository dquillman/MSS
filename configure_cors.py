
import firebase_admin
from firebase_admin import credentials, storage
from google.cloud import storage as gcs

# Initialize Firebase (using service account or default credentials)
try:
    # Try to find service account key
    import os
    from pathlib import Path
    cred_path = Path("web/serviceAccountKey.json")
    if cred_path.exists():
        cred = credentials.Certificate(str(cred_path))
        firebase_admin.initialize_app(cred)
        print("Initialized with serviceAccountKey.json")
    else:
        firebase_admin.initialize_app()
        print("Initialized with default credentials")
except ValueError:
    pass # Already initialized

def configure_cors():
    bucket_name = 'mss-video-creator-app.firebasestorage.app'
    
    # Get the GCS client and bucket
    client = gcs.Client()
    bucket = client.get_bucket(bucket_name)
    
    # Define CORS policy
    cors_configuration = [
        {
            "origin": ["*"], # Allow all origins for now (or restrict to your domain)
            "method": ["GET", "PUT", "POST", "DELETE", "OPTIONS"],
            "responseHeader": ["Content-Type", "x-goog-resumable"],
            "maxAgeSeconds": 3600
        }
    ]
    
    # Set CORS
    bucket.cors = cors_configuration
    bucket.patch()
    
    print(f"CORS configuration set for bucket: {bucket_name}")
    print(f"Current CORS: {bucket.cors}")

if __name__ == "__main__":
    configure_cors()
