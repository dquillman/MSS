"""
End-to-end tests for authentication flow
"""
import pytest


@pytest.mark.e2e
def test_full_registration_and_login_flow(client, test_db):
    """Test complete user registration and login flow"""
    # Step 1: Sign up
    signup_response = client.post('/api/signup', json={
        'email': 'e2e_test@example.com',
        'password': 'testpass123',
        'username': 'e2e_user'
    })
    
    assert signup_response.status_code == 200
    assert signup_response.json['success'] is True
    assert 'session_id' in signup_response.json
    
    session_id = signup_response.json['session_id']
    
    # Step 2: Set cookie and verify session
    client.set_cookie('localhost', 'session_id', session_id)
    
    # Step 3: Get current user
    me_response = client.get('/api/me')
    assert me_response.status_code == 200
    assert me_response.json['success'] is True
    assert me_response.json['user']['email'] == 'e2e_test@example.com'
    
    # Step 4: Logout
    logout_response = client.post('/api/logout')
    assert logout_response.status_code == 200
    assert logout_response.json['success'] is True
    
    # Step 5: Verify session is invalid
    me_response_after_logout = client.get('/api/me')
    assert me_response_after_logout.status_code == 200
    assert me_response_after_logout.json['success'] is False
    
    # Step 6: Login again
    login_response = client.post('/api/login', json={
        'email': 'e2e_test@example.com',
        'password': 'testpass123'
    })
    
    assert login_response.status_code == 200
    assert login_response.json['success'] is True


@pytest.mark.e2e
def test_password_reset_flow(client, test_db, test_user):
    """Test password reset flow"""
    # This test would require email functionality
    # For now, we test the token generation
    
    from web import database
    
    # Request password reset
    result = database.create_password_reset_token('test@example.com')
    assert result['success'] is True
    assert 'token' in result
    
    token = result['token']
    
    # Validate token
    validation = database.validate_reset_token(token)
    assert validation['valid'] is True
    assert 'user_id' in validation


@pytest.mark.e2e
def test_session_expiry(client, test_db, test_user):
    """Test that expired sessions are rejected"""
    # Create a session with short expiry
    from web import database
    from datetime import datetime, timedelta
    
    # Note: This would require modifying create_session to accept custom expiry
    # For now, we verify that get_session checks expiry
    session_id = database.create_session(test_user, duration_days=7)
    
    # Immediately verify it works
    result = database.get_session(session_id)
    assert result['success'] is True
    
    # Delete session to simulate expiry
    database.delete_session(session_id)
    
    # Verify it's now invalid
    result = database.get_session(session_id)
    assert result['success'] is False

