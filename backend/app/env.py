"""Central configuration, read from the environment once at import.

Missing a required variable throws here, at startup, with a clear message —
instead of failing later with a cryptic DB/S3 error. The rest of the app can
therefore trust `env` to be complete.
"""

import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Env:
    # Server
    APP_ENV: str = os.environ.get("APP_ENV", "development")
    PORT: int = int(os.environ.get("PORT", "8000"))
    # Where the React app runs — needed for CORS + cookie handling.
    CLIENT_URL: str = os.environ.get("CLIENT_URL", "http://localhost:5173")

    # Auth / JWT
    JWT_ACCESS_SECRET: str = _required("JWT_ACCESS_SECRET")
    JWT_REFRESH_SECRET: str = _required("JWT_REFRESH_SECRET")
    JWT_ACCESS_EXPIRES_MIN: int = int(os.environ.get("JWT_ACCESS_EXPIRES_MIN", "15"))
    JWT_REFRESH_EXPIRES_DAYS: int = int(os.environ.get("JWT_REFRESH_EXPIRES_DAYS", "7"))

    # Redis — backs the revocable refresh-token sessions.
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # PostgreSQL
    PGHOST: str = _required("PGHOST")
    PGPORT: int = int(_required("PGPORT"))
    PGUSER: str = _required("PGUSER")
    PGPASSWORD: str = _required("PGPASSWORD")
    PGDATABASE: str = _required("PGDATABASE")

    # Object storage (MinIO in dev, S3/Spaces in prod)
    MINIO_ENDPOINT: str = _required("MINIO_ENDPOINT")
    MINIO_ROOT_USER: str = _required("MINIO_ROOT_USER")
    MINIO_ROOT_PASSWORD: str = _required("MINIO_ROOT_PASSWORD")
    MINIO_BUCKET: str = _required("MINIO_BUCKET")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


env = Env()
