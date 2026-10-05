"""Serialize shopping mutations and create durable, idempotent receipts."""

import hashlib
import json
from typing import Optional
from uuid import uuid4

from accounts.models import Customer
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Cart, Order, Product, Purchase

TOKEN_SALT = "shop.checkout.v1"


class ShoppingError(Exception):
    """An expected conflict that a customer can resolve by refreshing their cart."""


def cart_fingerprint(items: list) -> str:
    """Bind confirmation to exact cart rows, quantities and displayed prices."""
    payload = sorted(
        (item.pk, item.product_id, item.quantity, str(item.product.price))
        for item in items
    )
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def checkout_token(customer_id: int, items: list) -> str:
    """Issue a short-lived confirmation without storing mutable session state."""
    return signing.dumps(
        {"customer": customer_id, "key": str(uuid4()), "cart": cart_fingerprint(items)},
        salt=TOKEN_SALT,
    )


@transaction.atomic
def change_cart(
    customer_id: int,
    *,
    product_id: Optional[int] = None,
    cart_id: Optional[int] = None,
    quantity: Optional[int] = None,
    remove: bool = False
) -> None:
    """Serialize one customer's cart changes and enforce the resulting stock limit."""
    Customer.objects.select_for_update().get(pk=customer_id)
    item = None
    if cart_id is not None:
        item = get_object_or_404(Cart, pk=cart_id, customer_id=customer_id)
        product_id = item.product_id
    product = get_object_or_404(Product.objects.select_for_update(), pk=product_id)
    if remove:
        Cart.objects.filter(pk=cart_id, customer_id=customer_id).delete()
        return
    if item is None:
        item = Cart.objects.filter(
            customer_id=customer_id, product_id=product_id
        ).first()
        quantity = quantity + (item.quantity if item else 0)
    if not 1 <= quantity <= 5 or quantity > product.stock:
        raise ShoppingError("تعداد باید بین ۱ تا ۵ و حداکثر برابر موجودی محصول باشد.")
    Cart.objects.update_or_create(
        customer_id=customer_id, product_id=product_id, defaults={"quantity": quantity}
    )


@transaction.atomic
def place_order(customer_id: int, token: str) -> Order:
    """Lock customer then products in ID order; commit receipt, stock and cart together."""
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=1800)
        if payload["customer"] != customer_id:
            raise signing.BadSignature()
    except (signing.BadSignature, KeyError, TypeError, ValueError) as error:
        raise ShoppingError(
            "تأیید سفارش نامعتبر یا منقضی است. سبد خرید را تازه کنید."
        ) from error
    Customer.objects.select_for_update().get(pk=customer_id)
    existing = Order.objects.filter(
        customer_id=customer_id, checkout_key=payload["key"]
    ).first()
    if existing:
        return existing
    items = list(Cart.objects.filter(customer_id=customer_id).order_by("product_id"))
    products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=[item.product_id for item in items])
        .order_by("pk")
    }
    if not items or any(item.product_id not in products for item in items):
        raise ShoppingError("سبد خرید تغییر کرده یا خالی است. آن را بررسی کنید.")
    for item in items:
        item.product = products[item.product_id]
    if cart_fingerprint(items) != payload["cart"]:
        raise ShoppingError(
            "سبد خرید یا قیمت تغییر کرده است. مبلغ جدید را بررسی و دوباره تأیید کنید."
        )
    for item in items:
        if (
            not 1 <= item.quantity <= 5
            or item.quantity > item.product.stock
            or item.product.price <= 0
        ):
            raise ShoppingError(
                "موجودی کافی نیست یا تعداد نامعتبر است. سبد خرید را بررسی کنید."
            )
    total = sum(item.get_total_price() for item in items)
    order = Order.objects.create(
        customer_id=customer_id, checkout_key=payload["key"], total_price=total
    )
    for item in items:
        product = item.product
        Purchase.objects.create(
            order=order,
            customer_id=customer_id,
            product=product,
            seller_id=product.shop_owner_id,
            product_name=product.name,
            store_name=product.shop_owner.store_name,
            unit_price=product.price,
            quantity=item.quantity,
            total_price=item.get_total_price(),
        )
        product.stock -= item.quantity
        product.save(update_fields=["stock"])
    Cart.objects.filter(pk__in=[item.pk for item in items]).delete()
    return order


@transaction.atomic
def advance_order(order_id: int) -> None:
    """Allow staff to move an order forward without claiming a payment occurred."""
    order = Order.objects.select_for_update().get(pk=order_id)
    transitions = {
        Order.Status.PLACED: Order.Status.PROCESSING,
        Order.Status.PROCESSING: Order.Status.COMPLETED,
    }
    if order.status in transitions:
        order.status = transitions[order.status]
        order.save(update_fields=["status"])
