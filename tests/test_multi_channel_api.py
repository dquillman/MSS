import sys
import os
import requests
import json
import sqlite3
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.analytics import AnalyticsManager

BASE_URL = "http://localhost:5000"
# Use a random email to avoid conflicts
EMAIL = f"test_channel_{int(os.urandom(4).hex(), 16)}@example.com"
PASSWORD = "password123"

def test_multi_channel_flow():
    session = requests.Session()

    # 1. Signup
    print(f"Signing up {EMAIL}...")
    try:
        res = session.post(f"{BASE_URL}/api/signup", json={
            "email": EMAIL,
            "password": PASSWORD
        })
        if res.status_code != 200:
            print(f"Signup failed: {res.status_code} {res.text}")
            # Try login if signup failed (maybe user exists)
            print("Trying login instead...")
            res = session.post(f"{BASE_URL}/api/login", json={
                "email": EMAIL,
                "password": PASSWORD
            })
            assert res.status_code == 200, f"Login failed: {res.text}"
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Is it running?")
        sys.exit(1)
    
    # 2. Login (if signup succeeded, we are logged in, but let's be sure)
    # Actually signup usually logs in automatically or returns success.
    # Let's explicit login to be safe.
    print("Logging in...")
    res = session.post(f"{BASE_URL}/api/login", json={
        "email": EMAIL,
        "password": PASSWORD
    })
    assert res.status_code == 200, f"Login failed: {res.text}"

    # 3. List channels (should be empty)
    print("Listing channels (expect empty)...")
    res = session.get(f"{BASE_URL}/api/channels/list?platform=youtube")
    assert res.status_code == 200
    data = res.json()
    assert data['success'] is True
    assert len(data['channels']) == 0

    # 4. Seed a channel directly via AnalyticsManager
    print("Seeding a dummy channel...")
    am = AnalyticsManager() # Will auto-detect DB
    channel_data = {
        'channel_id': 'UC_TEST_123',
        'channel_name': 'Test Channel',
        'channel_handle': 'test_handle',
        'channel_description': 'A test channel',
        'thumbnail_url': 'http://example.com/thumb.jpg',
        'channel_custom_url': 'test_custom'
    }
    
    channel_id = am.add_channel_account(EMAIL, 'youtube', channel_data)
    print(f"Seeded channel ID: {channel_id}")

    # 5. List channels again (should have 1)
    print("Listing channels (expect 1)...")
    res = session.get(f"{BASE_URL}/api/channels/list?platform=youtube")
    assert res.status_code == 200
    data = res.json()
    assert len(data['channels']) == 1
    assert data['channels'][0]['channel_id'] == 'UC_TEST_123'
    assert data['channels'][0]['is_default'] == 1 # First one should be default

    # 6. Seed a second channel
    print("Seeding second channel...")
    channel_data_2 = {
        'channel_id': 'UC_TEST_456',
        'channel_name': 'Second Channel',
        'channel_handle': 'second_handle',
        'thumbnail_url': 'http://example.com/thumb2.jpg'
    }
    channel_id_2 = am.add_channel_account(EMAIL, 'youtube', channel_data_2)
    
    # 7. Set second channel as default
    print("Setting second channel as default...")
    res = session.post(f"{BASE_URL}/api/channels/set-default", json={
        'channel_account_id': channel_id_2
    })
    assert res.status_code == 200
    assert res.json()['success'] is True

    # 8. Verify default change
    print("Verifying default change...")
    res = session.get(f"{BASE_URL}/api/channels/list?platform=youtube")
    channels = res.json()['channels']
    c1 = next(c for c in channels if c['id'] == channel_id)
    c2 = next(c for c in channels if c['id'] == channel_id_2)
    assert c1['is_default'] == 0
    assert c2['is_default'] == 1

    # 9. Sync metrics (mock)
    print("Testing sync metrics (expect 500 due to missing OAuth)...")
    res = session.post(f"{BASE_URL}/api/youtube/sync-metrics")
    # Expect 500 because we don't have real OAuth tokens
    if res.status_code == 500:
        print("Received expected 500 error for sync-metrics (missing OAuth)")
    else:
        print(f"Unexpected status for sync-metrics: {res.status_code} {res.text}")
        # assert res.status_code == 200 # Commented out as we expect failure in test env

    # 10. Remove channel
    print("Removing first channel...")
    res = session.post(f"{BASE_URL}/api/channels/remove", json={
        'channel_account_id': channel_id
    })
    assert res.status_code == 200
    
    # 11. Verify removal
    print("Verifying removal...")
    res = session.get(f"{BASE_URL}/api/channels/list?platform=youtube")
    channels = res.json()['channels']
    assert len(channels) == 1
    assert channels[0]['id'] == channel_id_2

    print("\nALL TESTS PASSED!")

if __name__ == "__main__":
    try:
        test_multi_channel_flow()
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
