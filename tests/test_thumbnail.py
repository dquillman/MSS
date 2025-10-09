"""
Test script to generate a thumbnail with PIL text overlay
"""
import requests
import json

# Test data
test_data = {
    "title": "Gerrymandering Explained",
    "prompt": "Create a dramatic political map background showing red and blue states with puzzle piece shapes. NO TEXT OR WORDS. Focus on: {{title}}"
}

print("Testing thumbnail generation with PIL text overlay...")
print(f"Title: {test_data['title']}")

# Call API
response = requests.post(
    'http://localhost:5000/generate-ai-thumbnail',
    json=test_data,
    timeout=120
)

result = response.json()

if result['success']:
    print(f"\nSuccess! Generated {len(result['thumbnails'])} thumbnails:")
    for thumb in result['thumbnails']:
        print(f"  - {thumb['variation']}: {thumb['url']}")
else:
    print(f"\nError: {result.get('error')}")

print(json.dumps(result, indent=2))
