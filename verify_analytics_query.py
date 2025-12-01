
import sys
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Add web directory to path
sys.path.append(os.path.join(os.getcwd(), 'web'))

# Initialize Firebase (mimic web/firebase_db.py logic)
cred_path = os.path.join(os.getcwd(), 'web', 'serviceAccountKey.json')
if os.path.exists(cred_path):
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("[FIREBASE] Initialized with serviceAccountKey.json")
    except ValueError:
        pass
else:
    try:
        firebase_admin.initialize_app()
        print("[FIREBASE] Initialized with default credentials")
    except ValueError:
        pass

db = firestore.client()
TEST_EMAIL = 'davequillman@gmail.com'

print(f"Testing analytics query for: {TEST_EMAIL}")

try:
    # Mimic AnalyticsManager.get_user_videos query
    print("Running query: collection('videos').where('user_email', '==', email).order_by('created_at', DESC).limit(50)")
    
    docs = (db.collection('videos')
            .where('user_email', '==', TEST_EMAIL)
            .order_by('created_at', direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream())
    
    count = 0
    for doc in docs:
        count += 1
        data = doc.to_dict()
        print(f"Found video: {data.get('title')}")
        
    print(f"SUCCESS: Query returned {count} videos")

except Exception as e:
    print(f"FAILURE: Query failed with error: {e}")
    if "index" in str(e).lower():
        print("\n!!! MISSING INDEX DETECTED !!!")
        print("You need to create a composite index in Firestore:")
        print("Collection ID: videos")
        print("Fields:")
        print("  user_email: Ascending")
        print("  created_at: Descending")
