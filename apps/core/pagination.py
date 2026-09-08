from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """Standardized pagination class with rich metadata envelope."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data: Any) -> Response:
        assert self.page is not None
        page_size = self.get_page_size(self.request) or self.page_size
        total_count = self.page.paginator.count
        total_pages = self.page.paginator.num_pages

        return Response(
            {
                "success": True,
                "data": data,
                "meta": {
                    "page": self.page.number,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "total_count": total_count,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                },
            }
        )

    def get_paginated_response_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Custom OpenAPI schema representation for drf-spectacular."""
        return {
            "type": "object",
            "required": ["success", "data", "meta"],
            "properties": {
                "success": {
                    "type": "boolean",
                    "example": True,
                },
                "data": schema,
                "meta": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "example": 1},
                        "page_size": {"type": "integer", "example": 20},
                        "total_pages": {"type": "integer", "example": 5},
                        "total_count": {"type": "integer", "example": 100},
                        "next": {
                            "type": "string",
                            "nullable": True,
                            "format": "uri",
                            "example": "http://api.example.com/items/?page=2",
                        },
                        "previous": {
                            "type": "string",
                            "nullable": True,
                            "format": "uri",
                            "example": None,
                        },
                    },
                },
            },
        }
