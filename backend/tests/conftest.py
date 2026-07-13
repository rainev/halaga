"""Set the environment the app's config requires BEFORE any app module imports.

env.py reads (and validates) configuration at import time, so these must be in
place first. The values are throwaway — the pure valuation + jwt tests never open
a real DB/Redis/S3 connection.
"""

import os

os.environ.setdefault("JWT_ACCESS_SECRET", "test-access-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")
os.environ.setdefault("PGHOST", "localhost")
os.environ.setdefault("PGPORT", "5432")
os.environ.setdefault("PGUSER", "test")
os.environ.setdefault("PGPASSWORD", "test")
os.environ.setdefault("PGDATABASE", "test")
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("MINIO_ROOT_USER", "test")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "test")
os.environ.setdefault("MINIO_BUCKET", "test")
