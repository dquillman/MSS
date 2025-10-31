"""
Pytest configuration and fixtures for MSS tests
"""
import pytest
import tempfile
import os
import sys
from pathlib import Path
from flask import Flask

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from web.api_server import app as flask_app
    from web import database
except ImportError as e:
    pytest.skip(f"Could not import app: {e}", allow_module_level=True)


@pytest.fixture
def app():
    """Flask application fixture"""
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    yield flask_app


@pytest.fixture
def client(app):
    """Test client fixture"""
    return app.test_client()


@pytest.fixture
def test_db():
    """Create temporary test database"""
    import sqlite3
    from pathlib import Path
    
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    # Store original path
    original_db_path = database.DB_PATH
    database.DB_PATH = Path(db_path)
    
    # Initialize test database
    database.init_db()
    
    yield database
    
    # Cleanup
    database.DB_PATH = original_db_path
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def test_user(test_db):
    """Create a test user"""
    result = database.create_user(
        email='test@example.com',
        password='testpass123',
        username='testuser'
    )
    if result.get('success'):
        user_id = result.get('user_id')
        yield user_id
        # Cleanup: delete user (optional)
    else:
        pytest.fail(f"Failed to create test user: {result.get('error')}")


@pytest.fixture
def authenticated_client(client, test_user):
    """Client with authenticated session"""
    # Login to get session
    response = client.post('/api/login', json={
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    
    if response.status_code == 200 and response.json.get('success'):
        session_id = response.json.get('session_id')
        # Set cookie
        client.set_cookie('localhost', 'session_id', session_id)
        return client
    else:
        pytest.fail(f"Failed to authenticate test user: {response.json}")


@pytest.fixture
def mock_openai(monkeypatch):
    """Mock OpenAI API calls"""
    def mock_generate_topics(*args, **kwargs):
        return ['Topic 1', 'Topic 2', 'Topic 3']
    
    def mock_draft_from_topic(*args, **kwargs):
        return "This is a mock script for testing purposes."
    
    try:
        monkeypatch.setattr('scripts.make_video.openai_generate_topics', mock_generate_topics)
        monkeypatch.setattr('scripts.make_video.openai_draft_from_topic', mock_draft_from_topic)
    except ImportError:
        pass  # Mock will be set up when needed


@pytest.fixture
def mock_stripe(monkeypatch):
    """Mock Stripe API calls"""
    class MockStripe:
        @staticmethod
        def Customer():
            return type('Customer', (), {'id': 'cus_test123'})()
        
        @staticmethod
        def Subscription():
            return type('Subscription', (), {'id': 'sub_test123'})()
    
    try:
        monkeypatch.setattr('stripe.Customer', MockStripe.Customer)
        monkeypatch.setattr('stripe.Subscription', MockStripe.Subscription)
    except ImportError:
        pass

