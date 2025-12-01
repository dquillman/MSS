
import sys
import os
import json
from flask import session

# Add web directory to path
sys.path.append(os.path.join(os.getcwd(), 'web'))

# Mock environment variables if needed
os.environ['FLASK_ENV'] = 'development'
os.environ['SECRET_KEY'] = 'dev_secret_key'

try:
    from web.api_server import app, youtube_sync_metrics
    from web import firebase_db
    
    # Get a user email to test with
    db = firebase_db.get_db()
    # We'll just use the one from debug_youtube_sync.py output: davequillman@gmail.com
    TEST_EMAIL = 'davequillman@gmail.com'
    
    print(f"Testing sync for: {TEST_EMAIL}")
    
    with app.test_request_context('/api/youtube/sync-metrics', method='POST'):
        # Mock session
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {'email': TEST_EMAIL}
                
            # We can't easily mock the session for the direct function call unless we use the client
            # But the function calls _get_user_from_session which reads from session
            
            # Mock _get_user_from_session to bypass authentication
            def mock_get_user():
                return TEST_EMAIL, None, None
            
            # Patch the function in the module
            import web.api_server
            original_get_user = getattr(web.api_server, '_get_user_from_session', None)
            web.api_server._get_user_from_session = mock_get_user
            
            try:
                response = youtube_sync_metrics()
            finally:
                # Restore original if needed (though script ends anyway)
                if original_get_user:
                    web.api_server._get_user_from_session = original_get_user
            
            # Check response
            if hasattr(response, 'get_json'):
                print("Response JSON:", json.dumps(response.get_json(), indent=2))
            else:
                print("Response:", response)
                
            if response.status_code == 200:
                print("SUCCESS: Sync endpoint returned 200")
                
                # Check Firestore 'videos' collection
                docs = (db.collection('videos')
                        .where('user_email', '==', TEST_EMAIL)
                        .limit(5)
                        .stream())
                
                count = 0
                for doc in docs:
                    count += 1
                    data = doc.to_dict()
                    print(f"Found video: {data.get('title')} (Platform: {data.get('platform')}, Views: {data.get('views')})")
                    
                print(f"Total videos found in 'videos' collection: {count}")
                
            else:
                print(f"FAILURE: Sync endpoint returned {response.status_code}")

except Exception as e:
    print(f"EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
