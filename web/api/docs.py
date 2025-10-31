"""
OpenAPI/Swagger documentation for MSS API
"""
from flasgger import Swagger, swag_from
import os

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/api/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "MSS API",
        "description": "Many Sources Say - Video Automation Platform API Documentation",
        "version": "1.0.0",
        "contact": {
            "name": "MSS Support",
            "email": "support@mss.example.com"
        }
    },
    "basePath": "/api",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "sessionAuth": {
            "type": "apiKey",
            "name": "session_id",
            "in": "cookie",
            "description": "Session ID cookie for authentication"
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
            "name": "Platforms",
            "description": "Multi-platform publishing"
        },
        {
            "name": "Analytics",
            "description": "Video analytics and metrics"
        },
        {
            "name": "Assets",
            "description": "Avatars, logos, thumbnails"
        }
    ]
}


def init_swagger(app):
    """Initialize Swagger documentation"""
    try:
        swagger = Swagger(app, config=swagger_config, template=swagger_template)
        return swagger
    except Exception as e:
        import logging
        logging.warning(f"[DOCS] Swagger initialization failed: {e}")
        return None

