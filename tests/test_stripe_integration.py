import pytest
from unittest.mock import patch, MagicMock
from web.api_server import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_usage_endpoint(client):
    with patch('web.api_server._get_user_obj_from_session') as mock_get_user:
        mock_get_user.return_value = ({'id': 'test_user', 'email': 'test@example.com'}, None, None)
        
        with patch('web.firebase_db.can_create_video') as mock_can_create:
            mock_can_create.return_value = {
                'allowed': True,
                'stats': {
                    'subscription_tier': 'starter',
                    'videos_this_month': 5
                }
            }
            # Mock USAGE_LIMITS dynamically since it's imported
            with patch.dict('web.firebase_db.USAGE_LIMITS', {'starter': 30}):
                response = client.get('/api/usage')
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert data['usage']['tier'] == 'starter'
                assert data['usage']['videos_this_month'] == 5
                assert data['usage']['monthly_limit'] == 30
                assert data['usage']['videos_remaining'] == 25

def test_create_checkout_session(client):
    with patch('web.api_server._get_user_from_session') as mock_get_user_email, \
         patch('web.api_server._get_user_obj_from_session') as mock_get_user_obj, \
         patch('stripe.checkout.Session.create') as mock_stripe_create, \
         patch.dict('web.api_server.STRIPE_PRICES', {'starter': 'price_123'}):
        
        mock_get_user_email.return_value = ('test@example.com', None, None)
        mock_get_user_obj.return_value = ({'id': 'test_user'}, None, None)
        
        mock_session = MagicMock()
        mock_session.url = 'https://checkout.stripe.com/test'
        mock_stripe_create.return_value = mock_session

        response = client.post('/api/stripe/create-checkout-session', json={'plan': 'starter'})
        
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        assert response.get_json()['url'] == 'https://checkout.stripe.com/test'
        
        mock_stripe_create.assert_called_once()
        args, kwargs = mock_stripe_create.call_args
        assert kwargs['client_reference_id'] == 'test_user'
        assert kwargs['customer_email'] == 'test@example.com'
        assert kwargs['metadata']['plan'] == 'starter'
        assert kwargs['line_items'][0]['price'] == 'price_123'
