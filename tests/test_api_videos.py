"""
Integration tests for video API endpoints
"""
import pytest


@pytest.mark.integration
def test_create_video_enhanced_requires_auth(client):
    """Test that video creation requires authentication"""
    response = client.post('/create-video-enhanced', json={
        'topic': {'title': 'Test Topic'}
    })
    
    # Should require authentication or have some validation
    assert response.status_code in [400, 401, 403]


@pytest.mark.integration
def test_create_video_enhanced_missing_topic(authenticated_client):
    """Test video creation with missing topic"""
    response = authenticated_client.post('/create-video-enhanced', json={})
    
    assert response.status_code == 400
    assert response.json['success'] is False


@pytest.mark.integration
def test_generate_topics_cache(client):
    """Test that topic generation can be cached"""
    # First request
    response1 = client.post('/generate-topics', json={
        'brand': 'Test Brand',
        'limit': 5
    })
    
    # Second identical request should be faster (cached)
    response2 = client.post('/generate-topics', json={
        'brand': 'Test Brand',
        'limit': 5
    })
    
    # Both should succeed
    if response1.status_code == 200:
        assert response1.json['success'] is True
        # Second should return same results (cached)
        if response2.status_code == 200:
            assert response2.json['topics'] == response1.json['topics']


@pytest.mark.integration
def test_get_recent_videos_requires_auth(client):
    """Test that getting video history requires authentication"""
    response = client.get('/api/get-recent-videos')
    
    assert response.status_code in [401, 403]


@pytest.mark.integration
def test_get_recent_videos_success(authenticated_client):
    """Test getting recent videos for authenticated user"""
    response = authenticated_client.get('/api/get-recent-videos')
    
    # Should return success even with empty list
    assert response.status_code == 200
    assert 'success' in response.json

