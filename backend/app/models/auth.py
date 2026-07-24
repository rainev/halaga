"""Auth request/response schemas.

JSON is snake_case throughout (Python-idiomatic); the frontend client matches.
The password hash is never part of any response shape here.
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["user", "admin"]


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class GoogleCredential(BaseModel):
    """The ID token (a JWT) that Google Identity Services hands the browser after
    a successful "Sign in with Google". Verified server-side (see security/google)."""

    credential: str = Field(min_length=1)


class PublicUser(BaseModel):
    id: int
    email: EmailStr
    role: Role
    is_verified: bool


class AuthResponse(BaseModel):
    """Response for register / login / refresh. The refresh token is NOT here —
    it rides in an httpOnly cookie, never in the JSON body."""

    user: PublicUser
    access_token: str
