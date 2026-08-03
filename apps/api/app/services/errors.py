from typing import Any


class ServiceError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)

