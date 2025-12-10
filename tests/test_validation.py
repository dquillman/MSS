
import pytest
from unittest.mock import MagicMock, patch
import json
from web.api_server import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_login_validation(client):
    """Test validation for /api/login"""
    # 1. Valid Login
    resp = client.post('/api/login', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    # Should be 401/400 because we don't have real DB, but validation should PASS 
    # (i.e. not "Invalid input" error)
    # The current mock implementation returns 400 "Please use Google Sign-In" if ID token missing
    assert resp.status_code in [400, 401]
    assert "Invalid input" not in resp.get_json().get('error', '')

    # 2. Invalid Email
    resp = client.post('/api/login', json={
        'email': 'not-an-email',
        'password': 'password123'
    })
    assert resp.status_code == 400
    assert "Invalid input" in resp.get_json()['error']

    # 3. Short Password
    resp = client.post('/api/login', json={
        'email': 'test@example.com',
        'password': 'short'
    })
    assert resp.status_code == 400
    assert "Invalid input" in resp.get_json()['error']

def test_youtube_upload_validation(client):
    """Test validation for /api/platforms/upload/youtube"""
    with patch('web.api_server.platform_api') as mock_api, \
         patch('web.api_server._get_user_from_session') as mock_auth, \
         patch('web.api_server.analytics_manager') as mock_analytics:
        
        # Mock Auth
        mock_auth.return_value = ('test@example.com', None, None)
        mock_api.upload_to_youtube.return_value = {'success': True, 'video_id': '123'}

        # 1. Valid Request
        resp = client.post('/api/platforms/upload/youtube', json={
            'video_filename': 'video.mp4',
            'title': 'My Video Title',
            'privacy': 'private'
        })
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        # 2. Missing Filename
        resp = client.post('/api/platforms/upload/youtube', json={
            'title': 'My Video Title'
        })
        assert resp.status_code == 400
        assert "Invalid input" in resp.get_json()['error']

        # 3. Valid Scheduled Time
        resp = client.post('/api/platforms/upload/youtube', json={
            'video_filename': 'video.mp4',
            'title': 'My Video Title',
            'publish_at': '2025-01-01T12:00:00Z'
        })
        assert resp.status_code == 200

def test_tiktok_upload_validation(client):
    """Test validation for /api/platforms/upload/tiktok"""
    with patch('web.api_server.platform_api') as mock_api, \
         patch('web.api_server._get_user_from_session') as mock_auth, \
         patch('web.api_server.analytics_manager') as mock_analytics:
        
        # Mock Auth
        mock_auth.return_value = ('test@example.com', None, None)
        mock_api.upload_to_tiktok.return_value = {'success': True}

        # 1. Valid Request
        resp = client.post('/api/platforms/upload/tiktok', json={
            'video_filename': 'video.mp4',
            'title': 'My TikTok'
        })
        assert resp.status_code == 200

        # 2. Missing Title
        resp = client.post('/api/platforms/upload/tiktok', json={
            'video_filename': 'video.mp4'
        })
        assert resp.status_code == 400
        assert "Invalid input" in resp.get_json()['error']

def test_queue_publication_validation(client):
    """Test validation for /api/platforms/queue"""
    with patch('web.api_server.multi_platform') as mock_mp, \
         patch('web.api_server._get_user_from_session') as mock_auth:
        
        mock_auth.return_value = ('test@example.com', None, None)
        mock_mp.queue_publication.return_value = 'queue_123'

        # 1. Valid
        resp = client.post('/api/platforms/queue', json={
            'video_filename': 'video.mp4',
            'platforms': ['youtube', 'tiktok'],
            'title': 'My Title'
        })
        assert resp.status_code == 200
        assert resp.get_json()['queue_id'] == 'queue_123'

        # 2. Missing Platforms (empty list)
        resp = client.post('/api/platforms/queue', json={
            'video_filename': 'video.mp4',
            'title': 'My Title',
            'platforms': []
        })
        # Pydantic min_items=1 for platforms
        assert resp.status_code == 400
        assert "Invalid input" in resp.get_json()['error']
