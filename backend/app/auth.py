"""Accounts and sessions.

Passwords: scrypt from the standard library, with a random salt per user, compared in constant
time. Sessions: a signed, expiring token (HMAC-SHA256 over the user id and expiry) in an httpOnly,
SameSite=Lax cookie, so page scripts cannot read it and other sites cannot send it with forms.
Users live in data/users.json behind one class, so a database can replace it later.

Password reset: there is no email service in this version. With DEV_RESET_LINKS on (the default),
the reset link is written to the server log; turn it off in any shared deployment.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field

from .config import Settings

log = logging.getLogger("helpvisual.auth")

COOKIE = "hv_session"
SESSION_SECONDS = 7 * 24 * 3600
RESET_SECONDS = 3600
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- models ----------


class User(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    email: str
    name: str
    password_hash: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reset_hash: str | None = None
    reset_expires: float | None = None
    # Branding shown to customers on this account's guides.
    brand_name: str = ""
    brand_color: str = "#2f5bea"
    logo_url: str | None = None


class PublicUser(BaseModel):
    id: str
    email: str
    name: str
    brand_name: str = ""
    brand_color: str = "#2f5bea"
    logo_url: str | None = None


class Branding(BaseModel):
    brand_name: str = ""
    brand_color: str = "#2f5bea"
    logo_url: str | None = None


class ProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class PasswordRequest(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class BrandingRequest(BaseModel):
    brand_name: str = Field(default="", max_length=60)
    brand_color: str = Field(default="#2f5bea", pattern=r"^#[0-9a-fA-F]{6}$")


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class ForgotRequest(BaseModel):
    email: str = Field(max_length=200)


class ResetRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8, max_length=200)


def public(user: User) -> PublicUser:
    return PublicUser(id=user.id, email=user.email, name=user.name, brand_name=user.brand_name,
                      brand_color=user.brand_color, logo_url=user.logo_url)


def branding(user: User | None) -> Branding:
    if user is None:
        return Branding()
    return Branding(brand_name=user.brand_name, brand_color=user.brand_color, logo_url=user.logo_url)


# ---------- passwords and tokens ----------


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=2**14, r=8, p=1, dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class SessionSigner:
    def __init__(self, secret: bytes):
        self._secret = secret

    def issue(self, user_id: str, seconds: int = SESSION_SECONDS) -> str:
        payload = _b64(json.dumps({"u": user_id, "e": int(time.time()) + seconds}).encode())
        signature = _b64(hmac.new(self._secret, payload.encode(), hashlib.sha256).digest())
        return f"{payload}.{signature}"

    def verify(self, token: str) -> str | None:
        try:
            payload, signature = token.split(".")
            expected = _b64(hmac.new(self._secret, payload.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                return None
            data = json.loads(_unb64(payload))
        except (ValueError, TypeError):
            return None
        return data["u"] if data.get("e", 0) > time.time() else None


def load_secret(settings: Settings) -> bytes:
    """SECRET_KEY from .env, or a random key created once and kept in data/secret.key."""
    if settings.secret_key:
        return settings.secret_key.encode()
    path = Path(settings.data_dir) / "secret.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48))
    return path.read_text().strip().encode()


# ---------- storage ----------


class UserStore:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "users.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read(self) -> dict[str, User]:
        if not self.path.exists():
            return {}
        return {k: User(**v) for k, v in json.loads(self.path.read_text(encoding="utf-8")).items()}

    def _write(self, users: dict[str, User]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: v.model_dump() for k, v in users.items()}, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def by_id(self, user_id: str) -> User | None:
        with self._lock:
            return self._read().get(user_id)

    def by_email(self, email: str) -> User | None:
        with self._lock:
            return next((u for u in self._read().values() if u.email == email.strip().lower()), None)

    def save(self, user: User) -> User:
        with self._lock:
            users = self._read()
            users[user.id] = user
            self._write(users)
        return user


class LoginLimiter:
    """At most `attempts` failed logins per email in `window` seconds, to slow password guessing."""

    def __init__(self, attempts: int = 10, window: int = 900):
        self.attempts, self.window = attempts, window
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def blocked(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            recent = [t for t in self._failures.get(key, []) if now - t < self.window]
            self._failures[key] = recent
            return len(recent) >= self.attempts

    def fail(self, key: str) -> None:
        with self._lock:
            self._failures.setdefault(key, []).append(time.time())

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


# ---------- routes and dependencies ----------


def build_auth(settings: Settings):
    users = UserStore(settings.data_dir)
    signer = SessionSigner(load_secret(settings))
    limiter = LoginLimiter()
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    def set_session(response: Response, user: User) -> None:
        response.set_cookie(
            COOKIE, signer.issue(user.id), max_age=SESSION_SECONDS, httponly=True,
            samesite="lax", secure=settings.cookie_secure, path="/",
        )

    def optional_user(request: Request) -> User | None:
        token = request.cookies.get(COOKIE)
        user_id = signer.verify(token) if token else None
        return users.by_id(user_id) if user_id else None

    def current_user(user: User | None = Depends(optional_user)) -> User:
        if user is None:
            raise HTTPException(401, "Sign in to continue.")
        return user

    @router.post("/register", status_code=201)
    def register(body: RegisterRequest, response: Response) -> PublicUser:
        email = body.email.strip().lower()
        if not EMAIL.match(email):
            raise HTTPException(422, "Enter a valid email address.")
        if users.by_email(email):
            raise HTTPException(409, "An account with this email already exists. Sign in instead.")
        user = users.save(User(email=email, name=body.name.strip(), password_hash=hash_password(body.password)))
        set_session(response, user)
        return public(user)

    @router.post("/login")
    def login(body: LoginRequest, response: Response) -> PublicUser:
        email = body.email.strip().lower()
        if limiter.blocked(email):
            raise HTTPException(429, "Too many attempts. Wait 15 minutes, or reset your password.")
        user = users.by_email(email)
        if user is None or not verify_password(body.password, user.password_hash):
            limiter.fail(email)
            raise HTTPException(401, "Email or password is incorrect.")  # the same message either way
        limiter.clear(email)
        set_session(response, user)
        return public(user)

    @router.post("/logout", status_code=204)
    def logout(response: Response) -> None:
        response.delete_cookie(COOKIE, path="/")

    @router.get("/me")
    def me(user: User = Depends(current_user)) -> PublicUser:
        return public(user)

    @router.post("/forgot", status_code=202)
    def forgot(body: ForgotRequest) -> dict:
        user = users.by_email(body.email)
        if user is not None:
            token = secrets.token_urlsafe(32)
            user.reset_hash = hashlib.sha256(token.encode()).hexdigest()
            user.reset_expires = time.time() + RESET_SECONDS
            users.save(user)
            if settings.dev_reset_links:
                log.warning("DEVELOPMENT ONLY - password reset link for %s: %s/reset?token=%s",
                            user.email, settings.app_url.rstrip("/"), token)
        # The same answer whether or not the account exists, so emails cannot be probed.
        return {"message": "If an account exists for that email, a reset link has been sent."}

    @router.post("/reset", status_code=204)
    def reset(body: ResetRequest) -> None:
        token_hash = hashlib.sha256(body.token.encode()).hexdigest()
        with users._lock:
            match = next((u for u in users._read().values()
                          if u.reset_hash and hmac.compare_digest(u.reset_hash, token_hash)), None)
        if match is None or (match.reset_expires or 0) < time.time():
            raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
        match.password_hash = hash_password(body.password)
        match.reset_hash, match.reset_expires = None, None
        users.save(match)
        limiter.clear(match.email)

    @router.put("/profile")
    def update_profile(body: ProfileRequest, user: User = Depends(current_user)) -> PublicUser:
        user.name = body.name.strip()
        return public(users.save(user))

    @router.post("/password", status_code=204)
    def change_password(body: PasswordRequest, user: User = Depends(current_user)) -> None:
        if not verify_password(body.current_password, user.password_hash):
            raise HTTPException(400, "Your current password is not correct.")
        user.password_hash = hash_password(body.new_password)
        users.save(user)

    @router.put("/branding")
    def update_branding(body: BrandingRequest, user: User = Depends(current_user)) -> PublicUser:
        user.brand_name, user.brand_color = body.brand_name.strip(), body.brand_color.lower()
        return public(users.save(user))

    @router.post("/branding/logo")
    async def upload_logo(file: UploadFile = File(...), user: User = Depends(current_user)) -> PublicUser:
        """PNG or JPEG up to 1 MB. Re-encoded as PNG, which drops anything hidden in the original file."""
        import io as _io

        from PIL import Image, UnidentifiedImageError

        data = await file.read()
        if len(data) > 1024 * 1024:
            raise HTTPException(413, "Use a logo smaller than 1 MB.")
        try:
            image = Image.open(_io.BytesIO(data))
            if image.format not in ("PNG", "JPEG"):
                raise HTTPException(415, "Use a PNG or JPEG logo.")
            image = image.convert("RGBA")
        except UnidentifiedImageError as exc:
            raise HTTPException(415, "That file is not an image.") from exc
        image.thumbnail((512, 512))
        folder = Path(settings.data_dir) / "media" / "brand"
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{user.id}-{secrets.token_hex(4)}.png"  # a new name each time, so browsers show the new logo
        image.save(folder / name, format="PNG")
        user.logo_url = f"/media/brand/{name}"
        return public(users.save(user))

    @router.delete("/branding/logo")
    def remove_logo(user: User = Depends(current_user)) -> PublicUser:
        user.logo_url = None
        return public(users.save(user))

    return router, current_user, optional_user, users
