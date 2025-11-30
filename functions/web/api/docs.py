"""
API Documentation with Swagger/OpenAPI
"""
from flasgger import Swagger

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api-docs"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "MSS API",
        "description": "Many Sources Say - Video Creation Platform API",
        "version": "5.5.7",
        "contact": {
            "email": "support@mss.example.com"
        },
        "license": {
            "name": "Proprietary"
        }
    },
    "host": "localhost:5000",
    "basePath": "/",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "session_cookie": {
            "type": "apiKey",
            "name": "session_id",
            "in": "cookie",
            "description": "Session cookie authentication"
        }
    },
    "tags": [
        {
            "name": "Authentication",
            "description": "User authentication endpoints"
        },
        {
            "name": "Videos",
            "description": "Video creation and management"
        },
        {
            "name": "Analytics",
            "description": "Video analytics and metrics"
        },
        {
            "name": "Platforms",
            "description": "Multi-platform publishing"
        },
        {
            "name": "Trends",
            "description": "Trending topics and content calendar"
        }
    ]
}


def init_swagger(app):
    """Initialize Swagger documentation for Flask app"""
    try:
        Swagger(app, config=swagger_config, template=swagger_template)
        print("[SWAGGER] API documentation initialized at /api-docs")
    except Exception as e:
        print(f"[SWAGGER] Failed to initialize: {e}")
