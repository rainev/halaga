"""Create (or update) the admin user from ADMIN_EMAIL / ADMIN_PASSWORD.

Idempotent: safe to run repeatedly. Run via `python -m app.seed.admin` or
infrastructure/scripts/seed.sh.
"""

import os

from ..db import pool, query_one
from ..security.password import hash_password


def main() -> None:
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        raise SystemExit("ADMIN_EMAIL and ADMIN_PASSWORD must be set to seed the admin user")

    pool.open()
    admin = query_one(
        """
        INSERT INTO users (email, password_hash, role, is_verified)
        VALUES (%s, %s, 'admin', TRUE)
        ON CONFLICT (email) DO UPDATE
          SET password_hash = EXCLUDED.password_hash,
              role = 'admin',
              is_verified = TRUE,
              updated_at = now()
        RETURNING id, email, role
        """,
        (email, hash_password(password)),
    )
    print(f"Seeded admin user: {admin['email']} (id={admin['id']}, role={admin['role']})")
    pool.close()


if __name__ == "__main__":
    main()
