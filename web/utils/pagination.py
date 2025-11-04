"""
Pagination utilities for API responses
"""
from typing import List, Dict, Any, Optional
from math import ceil


def paginate_list(items: List[Any], page: int = 1, per_page: int = 20) -> Dict[str, Any]:
    """
    Paginate a list of items
    
    Args:
        items: List of items to paginate
        page: Page number (1-indexed)
        per_page: Items per page
    
    Returns:
        dict: {
            'items': [...],
            'pagination': {
                'page': 1,
                'per_page': 20,
                'total': 100,
                'pages': 5,
                'has_next': True,
                'has_prev': False
            }
        }
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    
    total = len(items)
    pages = ceil(total / per_page) if total > 0 else 1
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Slice items
    paginated_items = items[offset:offset + per_page]
    
    return {
        'items': paginated_items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': pages,
            'has_next': page < pages,
            'has_prev': page > 1
        }
    }


def parse_pagination_params(request) -> tuple[int, int]:
    """
    Parse pagination parameters from Flask request
    
    Args:
        request: Flask request object
    
    Returns:
        tuple: (page, per_page)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Validate bounds
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    if per_page > 100:  # Max items per page
        per_page = 100
    
    return page, per_page






