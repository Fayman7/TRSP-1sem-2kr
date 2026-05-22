from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

app = FastAPI()

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
