import os
import re
import time
import uuid
from datetime import datetime
from typing import Annotated, Optional

from dotenv import load_dotenv
from fastapi import Body, Cookie, Depends, FastAPI, Form, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, Signer
from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

load_dotenv()

app = FastAPI()

MODE = os.getenv("MODE", "dev").lower()
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-for-cookie-signing")
DOCS_USER = os.getenv("DOCS_USER", "")
DOCS_PASSWORD = os.getenv("DOCS_PASSWORD", "")
SESSION_SIGNER = Signer(SECRET_KEY)

SESSION_INACTIVITY_TIMEOUT = 300  # сессия истекает через 5 минут без активности
SESSION_EXTEND_AFTER = 180  # продление, если прошло >= 3 минут с последней активности
SESSION_COOKIE_MAX_AGE = 300  # max_age куки — 5 минут

VALID_USERS: dict[str, dict] = {
    "user123": {
        "password": "password123",
        "user_id": str(uuid.uuid4()),
        "profile": {
            "username": "user123",
            "email": "user123@example.com",
            "full_name": "Test User",
        },
    },
}
USERS_BY_ID: dict[str, dict] = {
    user["user_id"]: user for user in VALID_USERS.values()
}

SAMPLE_PRODUCT_1 = {
    "product_id": 123,
    "name": "Smartphone",
    "category": "Electronics",
    "price": 599.99,
}
SAMPLE_PRODUCT_2 = {
    "product_id": 456,
    "name": "Phone Case",
    "category": "Accessories",
    "price": 19.99,
}
SAMPLE_PRODUCT_3 = {
    "product_id": 789,
    "name": "Iphone",
    "category": "Electronics",
    "price": 1299.99,
}
SAMPLE_PRODUCT_4 = {
    "product_id": 101,
    "name": "Headphones",
    "category": "Accessories",
    "price": 99.99,
}
SAMPLE_PRODUCT_5 = {
    "product_id": 202,
    "name": "Smartwatch",
    "category": "Electronics",
    "price": 299.99,
}
SAMPLE_PRODUCTS = [
    SAMPLE_PRODUCT_1,
    SAMPLE_PRODUCT_2,
    SAMPLE_PRODUCT_3,
    SAMPLE_PRODUCT_4,
    SAMPLE_PRODUCT_5,
]


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    age: Optional[int] = Field(default=None, gt=0)
    is_subscribed: Optional[bool] = None


class LoginRequest(BaseModel):
    username: str = Field(..., examples=["user123"])
    password: str = Field(..., examples=["password123"])


class LoginResponse(BaseModel):
    message: str = Field(..., examples=["Login successful"])


ACCEPT_LANGUAGE_PATTERN = re.compile(
    r"^[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})?"
    r"(\s*;\s*q=(0(\.\d+)?|1(\.0+)?))?"
    r"(,\s*[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})?(\s*;\s*q=(0(\.\d+)?|1(\.0+)?))?)*$"
)


class CommonHeaders(BaseModel):
    user_agent: str = Field(..., description='Значение заголовка "User-Agent"')
    accept_language: str = Field(..., description='Значение заголовка "Accept-Language"')

    @field_validator("accept_language")
    @classmethod
    def validate_accept_language(cls, value: str) -> str:
        if not ACCEPT_LANGUAGE_PATTERN.fullmatch(value.strip()):
            raise ValueError(
                "Invalid Accept-Language format. Expected pattern like 'en-US,en;q=0.9,es;q=0.8'"
            )
        return value.strip()


def get_common_headers(
    user_agent: str = Header(..., alias="User-Agent"),
    accept_language: str = Header(..., alias="Accept-Language"),
) -> CommonHeaders:
    try:
        return CommonHeaders(user_agent=user_agent, accept_language=accept_language)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        raise HTTPException(
            status_code=400,
            detail=str(first_error.get("msg", "Invalid request headers")),
        ) from exc


def common_headers_to_dict(headers: CommonHeaders) -> dict[str, str]:
    return {
        "User-Agent": headers.user_agent,
        "Accept-Language": headers.accept_language,
    }


def verify_credentials(username: str, password: str) -> bool:
    user = VALID_USERS.get(username)
    return user is not None and user["password"] == password


def is_valid_user_id(user_id: str) -> bool:
    try:
        uuid.UUID(user_id)
        return True
    except ValueError:
        return len(user_id) >= 8 and user_id.isalnum()


def _decode_signed_value(value: str | bytes) -> str:
    return value.decode() if isinstance(value, bytes) else value


def create_signed_session_token(user_id: str, last_activity: int) -> str:
    payload = f"{user_id}.{last_activity}"
    signed = SESSION_SIGNER.sign(payload)
    return _decode_signed_value(signed)


def parse_signed_session_token(
    session_token: Optional[str],
) -> tuple[Optional[str], Optional[int], bool]:
    """Возвращает (user_id, last_activity, is_invalid). is_invalid=True при подделке."""
    if not session_token:
        return None, None, False
    session_token = _decode_signed_value(session_token)
    try:
        payload = SESSION_SIGNER.unsign(session_token)
    except BadSignature:
        return None, None, True
    payload = _decode_signed_value(payload)
    if "." not in payload:
        return None, None, True
    user_id, timestamp_str = payload.rsplit(".", 1)
    if not is_valid_user_id(user_id):
        return None, None, True
    try:
        last_activity = int(timestamp_str)
    except ValueError:
        return None, None, True
    return user_id, last_activity, False


def get_profile_by_user_id(user_id: str) -> Optional[dict]:
    user = USERS_BY_ID.get(user_id)
    return user["profile"] if user else None


def session_expired() -> JSONResponse:
    return JSONResponse(status_code=401, content={"message": "Session expired"})


def invalid_session() -> JSONResponse:
    return JSONResponse(status_code=401, content={"message": "Invalid session"})


def unauthorized() -> JSONResponse:
    return JSONResponse(status_code=401, content={"message": "Unauthorized"})


def set_session_cookie(response: Response, user_id: str, last_activity: int) -> None:
    response.set_cookie(
        key="session_token",
        value=create_signed_session_token(user_id, last_activity),
        httponly=True,
        max_age=SESSION_COOKIE_MAX_AGE,
        secure=MODE == "prod",
        samesite="lax",
    )


def validate_and_refresh_session(
    session_token: Optional[str],
    response: Response,
    now: Optional[int] = None,
) -> tuple[Optional[str], Optional[JSONResponse]]:
    """
    Проверяет сессию по серверному времени.
    Возвращает (user_id, error_response). При продлении обновляет куку в response.
    """
    if now is None:
        now = int(time.time())

    user_id, last_activity, is_invalid = parse_signed_session_token(session_token)
    if is_invalid:
        return None, invalid_session()
    if user_id is None or last_activity is None:
        return None, session_expired()

    elapsed = now - last_activity
    if elapsed >= SESSION_INACTIVITY_TIMEOUT:
        return None, session_expired()

    if SESSION_EXTEND_AFTER <= elapsed < SESSION_INACTIVITY_TIMEOUT:
        set_session_cookie(response, user_id, now)

    return user_id, None


def handle_create_user(user: UserCreate) -> dict:
    return user.model_dump()


@app.post("/create_user")
def create_user(user: UserCreate) -> dict:
    return handle_create_user(user)


@app.get("/products/search")
def search_products(
    keyword: str = Query(..., min_length=1),
    category: Optional[str] = None,
    limit: int = Query(default=10, ge=1),
) -> list[dict]:
    keyword_lower = keyword.lower()
    results = [
        product
        for product in SAMPLE_PRODUCTS
        if keyword_lower in product["name"].lower()
        and (category is None or product["category"] == category)
    ]
    return results[:limit]


@app.get("/product/{product_id}")
def get_product(product_id: int) -> dict:
    for product in SAMPLE_PRODUCTS:
        if product["product_id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail="Product not found")


def _login_response(
    response: Response,
    username: str,
    password: str,
) -> dict | JSONResponse:
    if not verify_credentials(username, password):
        return unauthorized()

    user_id = VALID_USERS[username]["user_id"]
    set_session_cookie(response, user_id, int(time.time()))
    return {"message": "Login successful"}


@app.post(
    "/login",
    response_model=LoginResponse,
    summary="Вход в систему",
    description="Передайте JSON в разделе **Request body** (не в Parameters).",
)
async def login(
    response: Response,
    credentials: LoginRequest = Body(
        ...,
        examples={
            "default": {
                "summary": "Демо-пользователь",
                "value": {"username": "user123", "password": "password123"},
            }
        },
    ),
):
    result = _login_response(response, credentials.username, credentials.password)
    if isinstance(result, JSONResponse):
        return result
    return LoginResponse(**result)


@app.post("/login/form", include_in_schema=False, response_model=None)
async def login_form(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    return _login_response(response, username, password)


def _profile_response(
    session_token: Optional[str],
    response: Response,
    now: Optional[int] = None,
):
    user_id, error = validate_and_refresh_session(session_token, response, now)
    if error is not None:
        return error
    profile = get_profile_by_user_id(user_id)
    if profile is None:
        return invalid_session()
    return profile


@app.get("/profile")
def get_profile(
    response: Response,
    session_token: Optional[str] = Cookie(default=None),
):
    return _profile_response(session_token, response)


@app.get("/user")
def get_user_profile(
    response: Response,
    session_token: Optional[str] = Cookie(default=None),
):
    return _profile_response(session_token, response)


@app.get("/headers")
def get_request_headers(
    headers: Annotated[CommonHeaders, Depends(get_common_headers)],
) -> dict[str, str]:
    return common_headers_to_dict(headers)


@app.get("/info")
def get_info(
    response: Response,
    headers: Annotated[CommonHeaders, Depends(get_common_headers)],
) -> dict:
    response.headers["X-Server-Time"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "message": "Добро пожаловать! Ваши заголовки успешно обработаны.",
        "headers": common_headers_to_dict(headers),
    }
