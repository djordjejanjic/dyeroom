"""Sign in with Apple or Google (OpenID Connect), no passwords.

The browser goes to the provider and comes back with a one-time code; the server trades
that code for an ID token, a signed statement of who the person is. Its signature is
checked against the provider's published keys, and its audience, issuer, expiry and nonce
against what was asked for.

Configuration (environment):
  DYEROOM_PUBLIC_URL             the site's address, e.g. https://dyeroom.app; sign-ins
                                   come back to <public url>/auth/<provider>/callback
  DYEROOM_GOOGLE_CLIENT_ID       an OAuth client of type "Web application" (Google Cloud console)
  DYEROOM_GOOGLE_CLIENT_SECRET
  DYEROOM_APPLE_CLIENT_ID        a Services ID with Sign in with Apple (Apple Developer account)
  DYEROOM_APPLE_TEAM_ID
  DYEROOM_APPLE_KEY_ID           a Sign in with Apple key ...
  DYEROOM_APPLE_PRIVATE_KEY      ... and its .p8 text, or DYEROOM_APPLE_PRIVATE_KEY_FILE its path
  DYEROOM_DEV_LOGIN=1            a "Test user" sign-in for local development, never in production
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt


class SignInError(Exception):
    pass


def _env(name):
    return os.environ.get(name, "").strip()


def _apple_secret():
    """Apple wants the client secret as a short-lived token signed with the team's key."""
    key = _env("DYEROOM_APPLE_PRIVATE_KEY").replace("\\n", "\n")
    if not key and _env("DYEROOM_APPLE_PRIVATE_KEY_FILE"):
        with open(_env("DYEROOM_APPLE_PRIVATE_KEY_FILE")) as f:
            key = f.read()
    now = int(time.time())
    return jwt.encode({"iss": _env("DYEROOM_APPLE_TEAM_ID"), "iat": now, "exp": now + 600,
                       "aud": "https://appleid.apple.com", "sub": _env("DYEROOM_APPLE_CLIENT_ID")},
                      key, algorithm="ES256", headers={"kid": _env("DYEROOM_APPLE_KEY_ID")})


PROVIDERS = {
    "apple": {
        "label": "Apple",
        "authorize": "https://appleid.apple.com/auth/authorize",
        "token": "https://appleid.apple.com/auth/token",
        "keys": "https://appleid.apple.com/auth/keys",
        "issuers": ("https://appleid.apple.com",),
        "scope": "name email",
        "client_id": lambda: _env("DYEROOM_APPLE_CLIENT_ID"),
        "secret": _apple_secret,
        "configured": lambda: all(_env(f"DYEROOM_APPLE_{k}") for k in ("CLIENT_ID", "TEAM_ID", "KEY_ID"))
            and bool(_env("DYEROOM_APPLE_PRIVATE_KEY") or _env("DYEROOM_APPLE_PRIVATE_KEY_FILE")),
    },
    "google": {
        "label": "Google",
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "keys": "https://www.googleapis.com/oauth2/v3/certs",
        "issuers": ("https://accounts.google.com", "accounts.google.com"),
        "scope": "openid email profile",
        "client_id": lambda: _env("DYEROOM_GOOGLE_CLIENT_ID"),
        "secret": lambda: _env("DYEROOM_GOOGLE_CLIENT_SECRET"),
        "configured": lambda: bool(_env("DYEROOM_GOOGLE_CLIENT_ID") and _env("DYEROOM_GOOGLE_CLIENT_SECRET")),
    },
}
_key_sets = {}


def enabled():
    """[(id, label)] of the sign-ins this server offers, Apple first."""
    found = [(name, p["label"]) for name, p in PROVIDERS.items() if p["configured"]()]
    if dev_login():
        found.append(("dev", "Test user"))
    return found


def dev_login():
    """The test sign-in, only ever on a development machine: never on a public https address or
    with real payments, whatever DYEROOM_DEV_LOGIN says."""
    production = _env("DYEROOM_PUBLIC_URL").startswith("https://") or \
        _env("DYEROOM_PADDLE_ENV").lower() == "production" or _env("DYEROOM_BILLING").lower() == "paddle"
    return _env("DYEROOM_DEV_LOGIN") in ("1", "true", "yes") and not production


def authorize_url(name, redirect_uri, state, nonce):
    p = PROVIDERS[name]
    query = {"client_id": p["client_id"](), "redirect_uri": redirect_uri, "response_type": "code",
             "scope": p["scope"], "state": state, "nonce": nonce}
    if name == "apple":
        query["response_mode"] = "form_post"  # required by Apple when asking for name or email
    else:
        query["prompt"] = "select_account"
    return f"{p['authorize']}?{urllib.parse.urlencode(query)}"


def verify(name, id_token, nonce):
    """The claims of an ID token from this provider, or SignInError."""
    p = PROVIDERS[name]
    if name not in _key_sets:
        _key_sets[name] = jwt.PyJWKClient(p["keys"], lifespan=3600)
    try:
        key = _key_sets[name].get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=p["client_id"](), leeway=60,
                            options={"require": ["iss", "sub", "aud", "exp", "iat"]})
    except jwt.PyJWTError as exc:
        raise SignInError(f"{p['label']} sign-in token not valid: {exc}") from exc
    if claims["iss"] not in p["issuers"]:
        raise SignInError(f"{p['label']} sign-in token from an unexpected issuer")
    if claims.get("nonce") != nonce:
        raise SignInError(f"{p['label']} sign-in token was not made for this sign-in")
    return claims


def identity(name, code, redirect_uri, nonce, apple_user=None):
    """Trade the code for an ID token and say who signed in: {subject, email, name}."""
    p = PROVIDERS[name]
    form = urllib.parse.urlencode({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
                                   "client_id": p["client_id"](), "client_secret": p["secret"]()}).encode()
    request = urllib.request.Request(p["token"], data=form, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            tokens = json.load(response)
    except (urllib.error.URLError, ValueError) as exc:
        raise SignInError(f"{p['label']} did not accept the sign-in code: {exc}") from exc
    if "id_token" not in tokens:
        raise SignInError(f"{p['label']} sent no ID token")
    claims = verify(name, tokens["id_token"], nonce)
    email = claims.get("email") if claims.get("email_verified") in (True, "true", None) else None
    display = claims.get("name")
    if name == "apple" and apple_user:  # only on the first sign-in, and only in the form, not the token
        try:
            parts = json.loads(apple_user).get("name") or {}
            display = " ".join(filter(None, (parts.get("firstName"), parts.get("lastName")))) or None
        except (ValueError, AttributeError):
            pass
    return {"subject": claims["sub"], "email": email, "name": display}
