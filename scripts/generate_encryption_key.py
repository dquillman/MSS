#!/usr/bin/env python3
"""
Generate an encryption key for MSS application

Usage:
    python scripts/generate_encryption_key.py

Output:
    A new encryption key that should be added to ENCRYPTION_KEY environment variable
"""
from web.utils.encryption import generate_encryption_key

if __name__ == '__main__':
    key = generate_encryption_key()
    
    print("=" * 70)
    print("MSS Encryption Key Generator")
    print("=" * 70)
    print()
    print("Generated encryption key:")
    print(key)
    print()
    print("Add this to your .env file:")
    print(f"ENCRYPTION_KEY={key}")
    print()
    print("⚠️  IMPORTANT:")
    print("   - Keep this key secret and secure")
    print("   - Never commit it to version control")
    print("   - If key is lost, encrypted tokens cannot be recovered")
    print("   - Use the same key across all instances for the same database")
    print("=" * 70)


