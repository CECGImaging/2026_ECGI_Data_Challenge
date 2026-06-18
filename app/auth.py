import os
import secrets

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


# Config for Keycloak OIDC
# ---
KEYCLOAK_SERVER_URL = os.environ.get( "KEYCLOAK_SERVER_URL" ).rstrip("/")
KEYCLOAK_REALM = os.environ.get( "KEYCLOAK_REALM" )
OIDC_CLIENT_ID = os.environ.get( "OIDC_CLIENT_ID" )
OIDC_CLIENT_SECRET = os.environ.get( "OIDC_CLIENT_SECRET" )
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8099").rstrip("/")
SESSION_SECRET = os.environ.get( "SESSION_SECRET" ) or secrets.token_urlsafe( 32 )
AUTH_ENABLED = os.environ.get( "AUTH_ENABLED", "false" ).lower() not in ( "false", "0", "no" )

# OIDC discovery document for the realm
OIDC_METADATA_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"

oauth = OAuth()
oauth.register(
    name="keycloak",
    server_metadata_url=OIDC_METADATA_URL,
    client_id=OIDC_CLIENT_ID,
    client_secret=OIDC_CLIENT_SECRET,
    client_kwargs={"scope": "openid profile email"},
)



# Util functions for authentication
# ---
def current_user(request: Request):
    """Return the logged-in user dict, or None. When auth is disabled (local
    dev only) a stand-in user is returned so the rest of the app works."""
    if not AUTH_ENABLED:
        return {"sub": "dev", "username": "dev", "email": "dev@local", "name": "Dev User"}
    return request.session.get("user")

def require_user(request: Request):
    """Dependency for API routes: 401 if not authenticated."""
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    return user



# API routes for authentication
# ---
@router.get("/login")
async def login(request: Request):
    # if authentication is disabled, redirect to the home page
    if not AUTH_ENABLED: return RedirectResponse(url="/")
    # else redirect to Keycloak for authentication
    redirect_uri = f"{APP_BASE_URL}/auth/callback"
    return await oauth.keycloak.authorize_redirect(request, redirect_uri)

@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    # Redirect through Keycloak's end-session endpoint
    if AUTH_ENABLED and KEYCLOAK_REALM:
        end_session = (
            f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
            f"?post_logout_redirect_uri={APP_BASE_URL}/&client_id={OIDC_CLIENT_ID}"
        )
        return RedirectResponse(url=end_session)
    return RedirectResponse(url="/")

@router.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.keycloak.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Login failed: {exc}")

    claims = token.get("userinfo") or {}
    request.session["user"] = {
        "sub": claims.get("sub"),
        "username": claims.get("preferred_username") or claims.get("email") or claims.get("sub"),
        "email": claims.get("email"),
        "name": claims.get("name"),
    }
    return RedirectResponse(url="/")
