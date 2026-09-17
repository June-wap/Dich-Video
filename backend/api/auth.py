"""Bootstrap endpoint for the local API auth token (security P0 - see the
project's checklist-bao-mat-truoc-dong-goi-17-09.md, item 1). backend/main.py's
request_boundary middleware requires every other request to carry the token
the backend generated at this process's own startup (via X-Local-Token, or
for the two request kinds that cannot set custom headers - <audio src>/<a
download> against GET /api/audio/{id} - a `?token=` query parameter instead)
- but the frontend has no way to already know a value the backend only just
generated randomly, so this one path is deliberately exempted from that
check (see AUTH_TOKEN_PATH in main.py).

The exemption does not mean "public": a request here that DOES present an
Origin header must have one matching Settings.cors_origins - never a page
loaded from anywhere else. This is intentionally a second, independent gate
from CORSMiddleware (which only controls whether the *browser* lets the
calling page *read* the response) - CORSMiddleware alone would still let the
request run server-side for a disallowed origin; checking Origin here
ourselves stops the token from ever being computed into a response at all
for such a request.

A request with NO Origin header at all is treated as same-origin-safe rather
than rejected. Two cases produce that: the historical dev setup (frontend on
:5173, backend on :8000 - a real cross-origin browser fetch, which always DOES
carry an Origin header, so this path is unaffected) and the newer "1 tiến
trình, 1 cổng" production mode (Settings.serve_frontend in backend/main.py,
frontend and backend on the same origin). Per the WHATWG Fetch spec, a
same-origin GET fetch simply never gets an Origin header attached by the
browser - only cross-origin or non-GET/HEAD requests do. Rejecting "no
Origin" would make the bootstrap endpoint permanently unreachable in that
production mode. This does not weaken the check: any browser page on a
*different* origin still can't read this response either way (blocked by
CORSMiddleware/SOP, regardless of what this endpoint itself decides to
return), and request.url.hostname is already restricted to loopback
addresses by the request_boundary middleware before this handler ever runs.
"""
from fastapi import APIRouter, Request

from backend.errors import ApplicationError, ErrorCode

router = APIRouter()


@router.get("/auth/token", tags=["auth"])
async def get_local_token(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    if not settings.require_local_token:
        # Feature disabled (default in every test and any dev run that
        # hasn't opted in via LOCAL_AI_REQUIRE_LOCAL_TOKEN - see
        # Settings.from_env()) - there is no token to hand out.
        raise ApplicationError(ErrorCode.NOT_FOUND)
    origin = request.headers.get("origin")
    # See this module's docstring: a *present but disallowed* Origin is
    # rejected; a *missing* Origin is treated as same-origin-safe (the
    # common case once Settings.serve_frontend is on).
    if origin is not None and origin not in settings.cors_origins:
        raise ApplicationError(ErrorCode.UNAUTHORIZED)
    token = getattr(request.app.state, "local_token", None)
    if not token:
        # Should not happen once require_local_token is True (main.py's
        # lifespan always generates one first) - defensive only.
        raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
    return {"token": token}
