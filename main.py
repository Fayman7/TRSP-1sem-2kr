import os
import uuid
from typing import Optional

from fastapi import Body, Cookie, FastAPI, Form, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, Signer
from pydantic import BaseModel, EmailStr, Field

app = FastAPI()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-for-cookie-signing")
SESSION_SIGNER = Signer(SECRET_KEY)
SESSION_MAX_AGE = 3600

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


def verify_credentials(username: str, password: str) -> bool:
    user = VALID_USERS.get(username)
    return user is not None and user["password"] == password


def is_valid_user_id(user_id: str) -> bool:
    try:
        uuid.UUID(user_id)
        return True
    except ValueError:
        return len(user_id) >= 8 and user_id.isalnum()


def create_signed_session_token(user_id: str) -> str:
    signed = SESSION_SIGNER.sign(user_id)
    return signed.decode() if isinstance(signed, bytes) else signed


def get_user_id_from_session_token(session_token: Optional[str]) -> Optional[str]:
    if not session_token:
        return None
    if isinstance(session_token, bytes):
        session_token = session_token.decode()
    try:
        user_id = SESSION_SIGNER.unsign(session_token)
    except BadSignature:
        return None
    if isinstance(user_id, bytes):
        user_id = user_id.decode()
    if not is_valid_user_id(user_id):
        return None
    return user_id


def get_profile_by_user_id(user_id: str) -> Optional[dict]:
    user = USERS_BY_ID.get(user_id)
    return user["profile"] if user else None


def unauthorized() -> JSONResponse:
    return JSONResponse(status_code=401, content={"message": "Unauthorized"})


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
    request: Request,
    response: Response,
    username: str,
    password: str,
) -> dict | JSONResponse:
    if not verify_credentials(username, password):
        return unauthorized()

    user_id = VALID_USERS[username]["user_id"]
    session_token = create_signed_session_token(user_id)
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=SESSION_MAX_AGE,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return {"message": "Login successful"}


@app.post(
    "/login",
    response_model=LoginResponse,
    summary="Вход в систему",
    description="Передайте JSON в разделе **Request body** (не в Parameters).",
)
async def login(
    response: Response,
    request: Request,
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
    result = _login_response(request, response, credentials.username, credentials.password)
    if isinstance(result, JSONResponse):
        return result
    return LoginResponse(**result)


@app.post("/login/form", include_in_schema=False, response_model=None)
async def login_form(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    return _login_response(request, response, username, password)


def _profile_response(session_token: Optional[str]):
    user_id = get_user_id_from_session_token(session_token)
    if user_id is None:
        return unauthorized()
    profile = get_profile_by_user_id(user_id)
    if profile is None:
        return unauthorized()
    return profile


@app.get("/profile")
def get_profile(session_token: Optional[str] = Cookie(default=None)):
    return _profile_response(session_token)


@app.get("/user")
def get_user_profile(session_token: Optional[str] = Cookie(default=None)):
    return _profile_response(session_token)
