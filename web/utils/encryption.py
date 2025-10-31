"""
Encryption utilities for securing sensitive data (OAuth tokens, API keys)
"""
import os
import logging
from typing import Optional
from cryptography.fernet import Fernet
from base64 import b64encode, b64decode

logger = logging.getLogger(__name__)

# Global encryption key (loaded from environment)
_encryption_key: Optional[bytes] = None


def get_encryption_key() -> bytes:
    """Get or generate encryption key from environment"""
    global _encryption_key
    
    if _encryption_key is not None:
        return _encryption_key
    
    key_str = os.getenv('ENCRYPTION_KEY')
    if not key_str:
        logger.warning("[ENCRYPTION] ENCRYPTION_KEY not set. Encryption disabled.")
        return None
    
    try:
        _encryption_key = key_str.encode()
        # Validate it's a valid Fernet key
        Fernet(_encryption_key)
        return _encryption_key
    except Exception as e:
        logger.error(f"[ENCRYPTION] Invalid ENCRYPTION_KEY: {e}")
        return None


def encrypt_token(token: str) -> Optional[str]:
    """
    Encrypt a token using Fernet (AES-128 in CBC mode)
    
    Args:
        token: Plaintext token to encrypt
    
    Returns:
        Encrypted token (base64 encoded) or None if encryption disabled
    """
    key = get_encryption_key()
    if not key:
        logger.warning("[ENCRYPTION] Encryption disabled, returning plaintext (INSECURE)")
        return token  # Fallback - not secure but won't break
    
    try:
        f = Fernet(key)
        encrypted = f.encrypt(token.encode('utf-8'))
        return b64encode(encrypted).decode('utf-8')
    except Exception as e:
        logger.error(f"[ENCRYPTION] Encryption failed: {e}")
        return None


def decrypt_token(encrypted_token: str) -> Optional[str]:
    """
    Decrypt a token
    
    Args:
        encrypted_token: Encrypted token (base64 encoded)
    
    Returns:
        Decrypted token or None if decryption failed
    """
    key = get_encryption_key()
    if not key:
        # If encryption was disabled, assume token is plaintext
        return encrypted_token
    
    try:
        f = Fernet(key)
        encrypted_bytes = b64decode(encrypted_token.encode('utf-8'))
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"[ENCRYPTION] Decryption failed: {e}")
        return None


def generate_encryption_key() -> str:
    """
    Generate a new encryption key for use in ENCRYPTION_KEY env var
    
    Returns:
        Base64-encoded encryption key
    """
    key = Fernet.generate_key()
    return key.decode('utf-8')


# For testing
if __name__ == '__main__':
    # Generate a key
    new_key = generate_encryption_key()
    print(f"New encryption key: {new_key}")
    print("\nAdd this to your .env file:")
    print(f"ENCRYPTION_KEY={new_key}")
    
    # Test encryption/decryption
    os.environ['ENCRYPTION_KEY'] = new_key
    test_token = "test_token_12345"
    encrypted = encrypt_token(test_token)
    print(f"\nOriginal: {test_token}")
    print(f"Encrypted: {encrypted}")
    
    decrypted = decrypt_token(encrypted)
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_token == decrypted}")


