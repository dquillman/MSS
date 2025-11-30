"""
Authentication service - Business logic for user authentication
"""
import logging
from typing import Optional, Dict, Any
from web import firebase_db as database

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication business logic"""
    
    def __init__(self):
        self.logger = logger
    
    def login(self, email: str, password: str, remember_me: bool = False) -> Dict[str, Any]:
        """
        Handle user login
        
        Returns:
            dict: {'success': bool, 'user': dict, 'session_id': str} or {'success': False, 'error': str}
        """
        # Verify user credentials
        result = database.verify_user(email, password)
        
        if not result.get('success'):
            return {'success': False, 'error': result.get('error', 'Invalid credentials')}
        
        user = result['user']
        
        # Create session
        session_id = database.create_session(
            user_id=user['id'],
            duration_days=7,
            remember_me=remember_me
        )
        
        return {
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'username': user.get('username'),
                'subscription_tier': user.get('subscription_tier', 'free')
            },
            'session_id': session_id
        }
    
    def signup(self, email: str, password: str, username: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle user signup
        
        Returns:
            dict: {'success': bool, 'user_id': int, 'session_id': str} or {'success': False, 'error': str}
        """
        # Create user
        result = database.create_user(email, password, username=username)
        
        if not result.get('success'):
            return result
        
        user_id = result['user_id']
        
        # Auto-login after signup
        session_id = database.create_session(user_id=user_id, duration_days=7)
        
        return {
            'success': True,
            'user_id': user_id,
            'session_id': session_id
        }
    
    def logout(self, session_id: str) -> Dict[str, Any]:
        """
        Handle user logout
        
        Returns:
            dict: {'success': bool}
        """
        return database.delete_session(session_id)
    
    def get_current_user(self, session_id: str) -> Dict[str, Any]:
        """
        Get current user from session
        
        Returns:
            dict: {'success': bool, 'user': dict} or {'success': False, 'error': str}
        """
        return database.get_session(session_id)
    
    def verify_session(self, session_id: str) -> bool:
        """
        Verify if session is valid
        
        Returns:
            bool: True if session is valid
        """
        result = database.get_session(session_id)
        return result.get('success', False)






