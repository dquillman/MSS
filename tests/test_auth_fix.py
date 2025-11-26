import requests
import json
import uuid

BASE_URL = "http://localhost:5000"

def test_signup_login():
    # Generate unique user
    unique_id = str(uuid.uuid4())[:8]
    email = f"test_{unique_id}@example.com"
    password = "password123"
    username = f"user_{unique_id}"

    print(f"Testing signup for {email}...")

    # 1. Test Signup
    signup_payload = {
        "email": email,
        "password": password,
        "username": username,
        "remember_me": False
    }

    try:
        resp = requests.post(f"{BASE_URL}/api/signup", json=signup_payload)
        print(f"Signup Status: {resp.status_code}")
        print(f"Signup Response: {resp.text}")
        
        if resp.status_code != 200:
            print("Signup failed!")
            return False
            
        data = resp.json()
        if not data.get("success"):
            print("Signup success=False in response")
            return False
            
        print("Signup successful!")
        
        # 2. Test Login (should work with same credentials)
        print("Testing login...")
        login_payload = {
            "email": email,
            "password": password,
            "remember_me": False
        }
        
        resp = requests.post(f"{BASE_URL}/api/login", json=login_payload)
        print(f"Login Status: {resp.status_code}")
        print(f"Login Response: {resp.text}")
        
        if resp.status_code != 200:
            print("Login failed!")
            return False
            
        data = resp.json()
        if not data.get("success"):
            print("Login success=False in response")
            return False
            
        print("Login successful!")
        return True

    except Exception as e:
        print(f"Test failed with exception: {e}")
        return False

if __name__ == "__main__":
    if test_signup_login():
        print("VERIFICATION PASSED")
        exit(0)
    else:
        print("VERIFICATION FAILED")
        exit(1)
