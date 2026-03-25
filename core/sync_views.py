"""
Batch sync endpoint for processing offline-queued mutations.
Accepts an array of operations and returns results for each.
"""
import json
import logging

from django.test import RequestFactory
from django.urls import resolve, Resolver404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class BatchSyncView(APIView):
    """
    POST /api/v1/sync/batch/

    Replays an offline mutation queue in a single authenticated request.
    Each operation is resolved and dispatched internally via Django's URL
    resolver, reusing the caller's authentication context.

    Body: {
        "operations": [
            {
                "id": "client-uuid",
                "method": "PATCH",
                "url": "/api/v1/dreams/tasks/123/",
                "body": {"status": "completed"},
                "idempotencyKey": "optional-key"
            },
            ...
        ]
    }

    Response: {
        "results": [
            {"id": "client-uuid", "status": 200, "body": {...}},
            {"id": "client-uuid", "status": 400, "body": {"error": "..."}},
        ],
        "total": 2
    }
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "sync"

    MAX_OPERATIONS = 50

    BLOCKED_PREFIXES = [
        "/api/v1/auth/",
        "/api/auth/",
        "/api/v1/subscriptions/",
        "/api/v1/store/purchase",
        "/api/v1/ai/",
        "/api/v1/users/delete-account",
        "/api/v1/users/2fa/",
        "/api/v1/gamification/streak-freeze",
    ]

    def post(self, request):
        operations = request.data.get("operations", [])
        if not isinstance(operations, list) or not operations:
            return Response(
                {"error": "operations must be a non-empty array"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(operations) > self.MAX_OPERATIONS:
            return Response(
                {"error": f"Maximum {self.MAX_OPERATIONS} operations per batch"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        factory = RequestFactory()
        results = []

        for op in operations:
            op_id = op.get("id", "")
            method = str(op.get("method", "GET")).upper()
            url = str(op.get("url", ""))
            body = op.get("body", {})

            # Block dangerous operations
            if any(url.startswith(p) for p in self.BLOCKED_PREFIXES):
                results.append({
                    "id": op_id,
                    "status": 403,
                    "body": {"error": "Operation not allowed in batch sync"},
                })
                continue

            # Only allow mutation methods
            if method not in ("POST", "PUT", "PATCH", "DELETE"):
                results.append({
                    "id": op_id,
                    "status": 405,
                    "body": {"error": f"Method {method} not allowed"},
                })
                continue

            try:
                match = resolve(url)
                json_body = json.dumps(body) if body else ""
                internal_req = factory.generic(
                    method,
                    url,
                    data=json_body,
                    content_type="application/json",
                )
                internal_req.user = request.user
                internal_req.META["HTTP_AUTHORIZATION"] = request.META.get(
                    "HTTP_AUTHORIZATION", ""
                )
                # Copy idempotency key if present
                idem_key = op.get("idempotencyKey")
                if idem_key:
                    internal_req.META["HTTP_X_IDEMPOTENCY_KEY"] = idem_key

                response = match.func(internal_req, *match.args, **match.kwargs)
                if hasattr(response, "render"):
                    response.render()

                resp_body = {}
                if hasattr(response, "data"):
                    resp_body = response.data
                elif response.content:
                    try:
                        resp_body = json.loads(response.content)
                    except (json.JSONDecodeError, ValueError):
                        resp_body = {}

                results.append({
                    "id": op_id,
                    "status": response.status_code,
                    "body": resp_body,
                })

            except Resolver404:
                results.append({
                    "id": op_id,
                    "status": 404,
                    "body": {"error": f"URL not found: {url}"},
                })
            except Exception as e:
                logger.warning(
                    "Batch sync op failed: %s %s — %s", method, url, str(e)
                )
                results.append({
                    "id": op_id,
                    "status": 500,
                    "body": {"error": "Internal error"},
                })

        return Response({"results": results, "total": len(results)})
