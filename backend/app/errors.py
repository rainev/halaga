"""Application errors that carry an HTTP status.

Services and routers raise `AppError`; the handler registered in main.py reads
`.status` to shape a consistent JSON response. Kept separate from FastAPI's
HTTPException so the domain layer has no web-framework dependency.
"""


class AppError(Exception):
    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.message = message
        self.status = status
