from firebase_functions import https_fn
from web.api_server import app

@https_fn.on_request(max_instances=10, region="us-central1")
def api(req: https_fn.Request) -> https_fn.Response:
    with app.request_context(req.environ):
        return app.full_dispatch_request()
