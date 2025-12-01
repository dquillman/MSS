
import sys
import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# Add web directory to path
sys.path.append(os.path.join(os.getcwd(), 'web'))

# Initialize Firebase
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
DAYS = 30

print(f"Testing dashboard stats query for: {TEST_EMAIL} (Last {DAYS} days)")

try:
    start_date = datetime.utcnow() - timedelta(days=DAYS)
    print(f"Start Date: {start_date}")

    # Mimic AnalyticsManager.get_dashboard_stats query
    print("Running query: collection('videos').where('user_email', '==', email).where('created_at', '>=', start_date)")
    
    docs = (db.collection('videos')
            .where('user_email', '==', TEST_EMAIL)
            .where('created_at', '>=', start_date)
            .stream())
    
    count = 0
    total_views = 0
    for doc in docs:
        count += 1
        data = doc.to_dict()
        print(f"Found video: {data.get('title')} | Created: {data.get('created_at')} | Views: {data.get('views')}")
        total_views += data.get('views', 0)
        
    print(f"SUCCESS: Query returned {count} videos with {total_views} total views")

except Exception as e:
    print(f"FAILURE: Query failed with error: {e}")
