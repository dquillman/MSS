import requests

url = "https://mss-video-creator-app.web.app/api/oauth/youtube/authorize"
try:
    response = requests.get(url, allow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 302:
        location = response.headers.get('Location')
        print(f"Location: {location}")
        
        # Parse the location to find redirect_uri param
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(location)
        qs = parse_qs(parsed.query)
        redirect_uri = qs.get('redirect_uri', [''])[0]
        print(f"Redirect URI param: {redirect_uri}")
    else:
        print("Response was not a redirect.")
        print(response.text[:500])
except Exception as e:
    print(f"Error: {e}")
