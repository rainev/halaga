"""A single shared Redis client for the process.

`decode_responses=True` so we get str back instead of bytes. The connection is
lazy — no socket opens until the first command runs (login / refresh / logout).
"""

import redis

from .env import env

client = redis.Redis.from_url(env.REDIS_URL, decode_responses=True)
