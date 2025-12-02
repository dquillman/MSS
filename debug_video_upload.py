import requests
import io

# Create a dummy video file in memory
dummy_video = io.BytesIO(b'fake video content')
dummy_video.name = 'test_video.mp4'

files = {'video': ('test_video.mp4', dummy_video, 'video/mp4')}
headers = {'X-Debug-User': 'true'}

try:
    response = requests.post('http://127.0.0.1:5000/api/upload/video', files=files, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
