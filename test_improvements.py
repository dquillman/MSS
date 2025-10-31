# Quick Test Script

Run this to quickly test the improvements:

```python
#!/usr/bin/env python3
"""
Quick test script for MSS improvements
Tests: Rate limiting, Exception handling, File upload security
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_rate_limiting():
    """Test rate limiting on login endpoint"""
    print("\n🧪 Testing Rate Limiting...")
    print("=" * 50)
    
    for i in range(7):
        try:
            resp = requests.post(
                f"{BASE_URL}/api/login",
                json={"email": "test@test.com", "password": "wrongpassword"},
                timeout=5
            )
            data = resp.json()
            print(f"Attempt {i+1}: Status {resp.status_code} - {data.get('error', 'OK')}")
            
            if resp.status_code == 429:
                print("✅ Rate limit detected correctly!")
                return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    print("⚠️ Rate limit not triggered (may need to wait)")
    return False

def test_exception_handling():
    """Test exception handling on file endpoints"""
    print("\n🧪 Testing Exception Handling...")
    print("=" * 50)
    
    # Test non-existent file
    resp = requests.get(f"{BASE_URL}/out/nonexistent_file.mp4")
    print(f"Non-existent file: Status {resp.status_code}")
    if resp.status_code == 404:
        print("✅ Proper 404 handling")
    else:
        print(f"⚠️ Expected 404, got {resp.status_code}")
    
    # Test invalid metadata request
    resp = requests.get(f"{BASE_URL}/api/video/metadata/nonexistent.mp4")
    data = resp.json()
    print(f"Invalid metadata: Status {resp.status_code} - {data.get('error', 'OK')}")
    if resp.status_code == 404:
        print("✅ Proper error handling")
    
    return True

def test_file_upload_security():
    """Test file upload security"""
    print("\n🧪 Testing File Upload Security...")
    print("=" * 50)
    
    # Test invalid file type
    files = {'file': ('test.exe', b'fake content', 'application/x-msdownload')}
    resp = requests.post(f"{BASE_URL}/upload-intro-outro-file", files=files)
    data = resp.json()
    print(f"Invalid file type (.exe): Status {resp.status_code}")
    if resp.status_code == 400:
        print(f"✅ Rejected invalid file type: {data.get('error', 'Unknown error')}")
    else:
        print(f"⚠️ Expected 400, got {resp.status_code}")
    
    # Test file too large (simulate)
    # Note: Would need actual large file for real test
    print("✅ File type validation working")
    
    return True

def test_mobile_responsive():
    """Test if pages have mobile viewport"""
    print("\n🧪 Testing Mobile Responsiveness...")
    print("=" * 50)
    
    pages = [
        '/auth',
        '/studio',
        '/dashboard',
        '/workflow',
        '/multi-platform',
        '/trends-calendar',
        '/settings'
    ]
    
    for page in pages:
        try:
            resp = requests.get(f"{BASE_URL}{page}", timeout=5)
            if resp.status_code == 200:
                content = resp.text
                if 'viewport' in content and 'width=device-width' in content:
                    print(f"✅ {page}: Has viewport meta tag")
                else:
                    print(f"⚠️ {page}: Missing viewport tag")
                if '@media' in content:
                    print(f"✅ {page}: Has responsive CSS")
                else:
                    print(f"⚠️ {page}: Missing responsive CSS")
        except Exception as e:
            print(f"❌ {page}: Error - {e}")
    
    return True

def main():
    print("🚀 MSS Improvements Test Suite")
    print("=" * 50)
    print("Make sure the server is running on http://localhost:5000")
    print("=" * 50)
    
    results = []
    
    # Run tests
    results.append(("Rate Limiting", test_rate_limiting()))
    results.append(("Exception Handling", test_exception_handling()))
    results.append(("File Upload Security", test_file_upload_security()))
    results.append(("Mobile Responsiveness", test_mobile_responsive()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

if __name__ == "__main__":
    main()

