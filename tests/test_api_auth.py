"""
Integration tests for authentication API endpoints
"""
import pytest


@pytest.mark.integration
def test_login_success(client, test_db, test_user):
    """Test successful login"""
    response = client.post('/api/login', json={
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'session_id' in response.json
    assert 'user' in response.json


@pytest.mark.integration
def test_login_wrong_password(client, test_db, test_user):
    """Test login with wrong password"""
    response = client.post('/api/login', json={
        'email': 'test@example.com',
        'password': 'wrongpassword'
    })
    
    assert response.status_code == 401
    assert response.json['success'] is False
    assert 'error' in response.json


@pytest.mark.integration
def test_login_nonexistent_user(client, test_db):
    """Test login with non-existent user"""
    response = client.post('/api/login', json={
        'email': 'nonexistent@example.com',
        'password': 'anypassword'
    })
    
    assert response.status_code == 401
    assert response.json['success'] is False


@pytest.mark.integration
def test_login_validation_error(client, test_db):
    """Test login with invalid input (missing password)"""
    response = client.post('/api/login', json={
        'email': 'test@example.com'
        # Missing password
    })
    
    assert response.status_code == 400
    assert response.json['success'] is False
    assert 'error' in response.json


@pytest.mark.integration
def test_login_invalid_email_format(client, test_db):
    """Test login with invalid email format"""
    response = client.post('/api/login', json={
        'email': 'not-an-email',
        'password': 'password123'
    })
    
    assert response.status_code == 400
    assert response.json['success'] is False


@pytest.mark.integration
def test_signup_success(client, test_db):
    """Test successful signup"""
    response = client.post('/api/signup', json={
        'email': 'newuser@example.com',
        'password': 'password123',
        'username': 'newuser'
    })
    
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'session_id' in response.json
    assert 'user_id' in response.json


@pytest.mark.integration
def test_signup_duplicate_email(client, test_db, test_user):
    """Test signup with duplicate email"""
    response = client.post('/api/signup', json={
        'email': 'test@example.com',  # Already exists
        'password': 'password123'
    })
    
    assert response.status_code == 400
    assert response.json['success'] is False


@pytest.mark.integration
def test_signup_weak_password(client, test_db):
    """Test signup with weak password"""
    response = client.post('/api/signup', json={
        'email': 'user@example.com',
        'password': 'short'  # Too short
    })
    
    assert response.status_code == 400
    assert response.json['success'] is False


@pytest.mark.integration
def test_logout_success(authenticated_client):
    """Test successful logout"""
    response = authenticated_client.post('/api/logout')
    
    assert response.status_code == 200
    assert response.json['success'] is True


@pytest.mark.integration
def test_get_current_user(authenticated_client):
    """Test getting current user info"""
    response = authenticated_client.get('/api/me')
    
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'user' in response.json
    assert response.json['user']['email'] == 'test@example.com'

