"""
Unit tests for database session management functions
"""
import pytest
from datetime import datetime, timedelta
from web import database


@pytest.mark.unit
def test_create_session_success(test_db, test_user):
    """Test successful session creation"""
    session_id = database.create_session(
        user_id=test_user,
        duration_days=7
    )
    assert session_id is not None
    assert len(session_id) > 0
    
    # Verify session exists
    result = database.get_session(session_id)
    assert result['success'] is True
    assert result['user']['id'] == test_user


@pytest.mark.unit
def test_create_session_remember_me(test_db, test_user):
    """Test session creation with remember_me option"""
    session_id = database.create_session(
        user_id=test_user,
        duration_days=7,
        remember_me=True
    )
    assert session_id is not None
    
    # Verify session exists (30 days expiry)
    result = database.get_session(session_id)
    assert result['success'] is True


@pytest.mark.unit
def test_get_session_valid(test_db, test_user):
    """Test retrieving valid session"""
    session_id = database.create_session(test_user)
    result = database.get_session(session_id)
    
    assert result['success'] is True
    assert 'user' in result
    assert result['user']['id'] == test_user


@pytest.mark.unit
def test_get_session_invalid(test_db):
    """Test retrieving invalid session"""
    result = database.get_session('invalid_session_id_12345')
    assert result['success'] is False
    assert 'error' in result


@pytest.mark.unit
def test_delete_session(test_db, test_user):
    """Test session deletion"""
    session_id = database.create_session(test_user)
    
    # Verify session exists
    result = database.get_session(session_id)
    assert result['success'] is True
    
    # Delete session
    delete_result = database.delete_session(session_id)
    assert delete_result['success'] is True
    
    # Verify session no longer exists
    result = database.get_session(session_id)
    assert result['success'] is False

