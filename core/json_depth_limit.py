"""
JSON depth limit middleware for DRF (V-304).

Prevents deeply nested JSON payloads from consuming excessive CPU/memory
during parsing. Python's default recursion limit (1000) provides some
protection, but a dedicated depth check is more explicit and catches
issues earlier.

Adds a custom DRF parser that enforces a max nesting depth.
"""

import json
import logging

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

logger = logging.getLogger(__name__)

# Maximum allowed JSON nesting depth
MAX_JSON_DEPTH = 20


def _check_depth(obj, current_depth=0, max_depth=MAX_JSON_DEPTH):
    """Recursively check JSON nesting depth. Raises ParseError if exceeded."""
    if current_depth > max_depth:
        raise ParseError(
            f"JSON nesting depth exceeds maximum of {max_depth} levels."
        )

    if isinstance(obj, dict):
        for value in obj.values():
            _check_depth(value, current_depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj:
            _check_depth(item, current_depth + 1, max_depth)


class DepthLimitedJSONParser(JSONParser):
    """
    JSONParser that rejects payloads with nesting deeper than MAX_JSON_DEPTH.

    Drop-in replacement for DRF's default JSONParser.
    """

    def parse(self, stream, media_type=None, parser_context=None):
        result = super().parse(stream, media_type=media_type, parser_context=parser_context)
        try:
            _check_depth(result)
        except ParseError:
            logger.warning("JSON depth limit exceeded (max %d levels)", MAX_JSON_DEPTH)
            raise
        return result
