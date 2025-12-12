# Cloud Function Entry Point - Force Rebuild 2025-12-11 17:01
from firebase_functions import https_fn

@https_fn.on_request(max_instances=10, region="us-central1", memory=1024)
def api(req: https_fn.Request) -> https_fn.Response:
    try:
        # Lazy import to catch import-time errors
        from web.api_server import app
        
        with app.request_context(req.environ):
            return app.full_dispatch_request()
    except Exception as e:
        import traceback
        return https_fn.Response(f"CRITICAL FUNCTION ERROR: {str(e)}\n{traceback.format_exc()}", status=500)
