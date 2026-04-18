from __future__ import annotations

import sys
import types
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

WORKER_SRC_DIR = Path(__file__).resolve().parents[2] / "worker" / "src"
if str(WORKER_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC_DIR))


if "itsdangerous" not in sys.modules:
    itsdangerous = types.ModuleType("itsdangerous")

    class BadSignature(Exception):
        pass

    class SignatureExpired(Exception):
        pass

    class URLSafeTimedSerializer:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def dumps(self, value):
            return str(value)

        def loads(self, value, max_age=None):
            del max_age
            return value

    itsdangerous.BadSignature = BadSignature
    itsdangerous.SignatureExpired = SignatureExpired
    itsdangerous.URLSafeTimedSerializer = URLSafeTimedSerializer
    sys.modules["itsdangerous"] = itsdangerous


if "argon2" not in sys.modules:
    argon2 = types.ModuleType("argon2")

    class PasswordHasher:
        def hash(self, password: str) -> str:
            return f"hashed:{password}"

        def verify(self, password_hash: str, password: str) -> bool:
            return password_hash == f"hashed:{password}"

    argon2.PasswordHasher = PasswordHasher
    sys.modules["argon2"] = argon2


if "argon2.exceptions" not in sys.modules:
    argon2_exceptions = types.ModuleType("argon2.exceptions")

    class InvalidHashError(Exception):
        pass

    class VerificationError(Exception):
        pass

    class VerifyMismatchError(Exception):
        pass

    argon2_exceptions.InvalidHashError = InvalidHashError
    argon2_exceptions.VerificationError = VerificationError
    argon2_exceptions.VerifyMismatchError = VerifyMismatchError
    sys.modules["argon2.exceptions"] = argon2_exceptions


if "pytesseract" not in sys.modules:
    pytesseract = types.ModuleType("pytesseract")
    pytesseract.Output = types.SimpleNamespace(DICT="dict")
    pytesseract.image_to_data = lambda *args, **kwargs: {"text": [], "left": [], "top": [], "width": [], "height": [], "conf": []}
    sys.modules["pytesseract"] = pytesseract


if "sse_starlette" not in sys.modules:
    sse_starlette = types.ModuleType("sse_starlette")
    sse_starlette_sse = types.ModuleType("sse_starlette.sse")

    class EventSourceResponse:
        def __init__(self, generator):
            self.generator = generator

    sse_starlette_sse.EventSourceResponse = EventSourceResponse
    sys.modules["sse_starlette"] = sse_starlette
    sys.modules["sse_starlette.sse"] = sse_starlette_sse
