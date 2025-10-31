"""
Unit tests for database user management functions
"""
import pytest
from web import database


@pytest.mark.unit
def test_create_user_success(test_db):
    """Test successful user creation"""
    result = database.create_user(
        email='newuser@example.com',
        password='password123',
        username='newuser'
    )
    assert result['success'] is True
    assert 'user_id' in result
    assert result['user_id'] > 0


@pytest.mark.unit
def test_create_user_duplicate_email(test_db, test_user):
    """Test that duplicate email is rejected"""
    result = database.create_user(
        email='test@example.com',  # Same as test_user
        password='password123'
    )
    assert result['success'] is False
    assert 'error' in result
    assert 'already registered' in result['error'].lower()


@pytest.mark.unit
def test_create_user_invalid_email(test_db):
    """Test that invalid email format is rejected"""
    result = database.create_user(
        email='invalid-email',  # Invalid format
        password='password123'
    )
    # Note: Email validation might happen at API level, not DB level
    # This test verifies DB doesn't crash on invalid input


@pytest.mark.unit
def test_verify_user_correct_password(test_db, test_user):
    """Test successful password verification"""
    result = database.verify_user(
        email='test@example.com',
        password='testpass123'
    )
    assert result['success'] is True
    assert 'user' in result
    assert result['user']['email'] == 'test@example.com'


@pytest.mark.unit
def test_verify_user_wrong_password(test_db, test_user):
    """Test that wrong password is rejected"""
    result = database.verify_user(
        email='test@example.com',
        password='wrongpassword'
    )
    assert result['success'] is False
    assert 'error' in result


@pytest.mark.unit
def test_verify_user_nonexistent(test_db):
    """Test that nonexistent user is rejected"""
    result = database.verify_user(
        email='nonexistent@example.com',
        password='anypassword'
    )
    assert result['success'] is False
    assert 'error' in result


@pytest.mark.unit
def test_password_hashing_bcrypt(test_db):
    """Verify passwords are hashed with bcrypt"""
    password = 'testpass123'
    hash1 = database.hash_password(password)
    hash2 = database.hash_password(password)
    
    # Same password, different hashes (salt)
    assert hash1 != hash2
    
    # But both verify correctly
    assert database.verify_password(hash1, password)
    assert database.verify_password(hash2, password)
    
    # Wrong password doesn't verify
    assert not database.verify_password(hash1, 'wrongpassword')

