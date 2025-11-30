import sys
import os

# Simulate Cloud Functions environment where 'functions' is the root
# We assume we are running from the 'functions' directory
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

print(f"CWD: {cwd}")
# print(f"Path: {sys.path}")

try:
    print("Attempting to import web.models.requests...")
    from web.models.requests import SignupRequest
    print("SUCCESS: Imported SignupRequest")
except Exception as e:
    print(f"ERROR: Failed to import SignupRequest: {e}")
    import traceback
    traceback.print_exc()
