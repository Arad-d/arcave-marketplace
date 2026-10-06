import logging

from accounts.middleware import shop_owner_required
from accounts.models import ShopOwner
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MessageForm, ProductForm, QuantityForm
from .models import Cart, Comment, Order, Product, Purchase, Reply
from .services import ShoppingError, change_cart, checkout_token, place_order

logger = logging.getLogger(__name__)


@login_required
def product_list(request):
    """Product listing with search and category filter - requires authentication."""
    query = request.GET.get("q", "")
    category = request.GET.get("category", "")

    products = Product.objects.all()

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    if category:
        products = products.filter(category=category)

    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "shop/product_list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "category": category,
            "categories": Product.CATEGORY_CHOICES,
        },
    )


def product_detail(request, pk):
    """Product detail page with comments."""
    product = get_object_or_404(Product, pk=pk)
    comments = product.comments.select_related("customer").prefetch_related("reply")

    # Check if user has purchased this product
    has_purchased = False
    purchase_quantity = 0
    if request.user.is_authenticated:
        purchases = Purchase.objects.filter(
            product=product, customer=request.user
        ).aggregate(total=Sum("quantity"))
        purchase_quantity = purchases["total"] or 0
        has_purchased = purchase_quantity > 0

    return render(
        request,
        "shop/product_detail.html",
        {
            "product": product,
            "comments": comments,
            "has_purchased": has_purchased,
            "purchase_quantity": purchase_quantity,
        },
    )


@login_required
@require_POST
def add_to_cart(request, pk):
    """Add validated units without exceeding the resulting cart or stock limit."""
    form = QuantityForm(request.POST)
    if form.is_valid():
        try:
            change_cart(
                request.user.pk, product_id=pk, quantity=form.cleaned_data["quantity"]
            )
            messages.success(request, "سبد خرید به‌روزرسانی شد.")
        except ShoppingError as error:
            messages.error(request, str(error))
    else:
        messages.error(request, "تعداد باید یک عدد صحیح بین ۱ تا ۵ باشد.")
    return redirect("product_detail", pk=pk)


@login_required
def view_cart(request):
    """Display shopping cart."""
    cart_items = list(
        Cart.objects.filter(customer=request.user).select_related("product")
    )

    # Calculate totals
    total_items = sum(item.quantity for item in cart_items)
    total_price = sum(item.get_total_price() for item in cart_items)

    return render(
        request,
        "shop/cart.html",
        {
            "cart_items": cart_items,
            "total_items": total_items,
            "total_price": total_price,
            "checkout_token": checkout_token(request.user.pk, cart_items),
        },
    )


@login_required
@require_POST
def update_cart(request, pk):
    """Update an owned cart with validated quantities."""
    get_object_or_404(Cart, pk=pk, customer=request.user)
    form = QuantityForm(request.POST)
    if form.is_valid():
        try:
            change_cart(
                request.user.pk, cart_id=pk, quantity=form.cleaned_data["quantity"]
            )
            messages.success(request, "سبد خرید به‌روزرسانی شد.")
        except ShoppingError as error:
            messages.error(request, str(error))
    else:
        messages.error(request, "تعداد باید یک عدد صحیح بین ۱ تا ۵ باشد.")
    return redirect("view_cart")


@login_required
@require_POST
def remove_from_cart(request, pk):
    """Remove an owned item under the same lock used by checkout."""
    change_cart(request.user.pk, cart_id=pk, remove=True)
    messages.success(request, "مورد از سبد خرید حذف شد.")
    return redirect("view_cart")


@login_required
@require_POST
def checkout(request):
    """Confirm the displayed cart once, returning the same receipt on retries."""
    try:
        order = place_order(request.user.pk, request.POST.get("checkout_token", ""))
    except ShoppingError as error:
        messages.error(request, str(error))
        return redirect("view_cart")
    except DatabaseError:
        logger.exception("Checkout transaction failed", extra={"request": request})
        messages.error(request, "ثبت سفارش انجام نشد. دوباره تلاش کنید.")
        return redirect("view_cart")
    messages.success(request, "سفارش ثبت شد. پرداخت آنلاین در این نسخه فعال نیست.")
    return redirect("order_detail", number=order.number)


@login_required
def order_detail(request, number):
    """Show a receipt only to the customer who placed the order."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), number=number, customer=request.user
    )
    return render(request, "shop/order_detail.html", {"order": order})


@login_required
def customer_dashboard(request):
    """Customer dashboard with purchases and browsing."""
    purchases = Purchase.objects.filter(customer=request.user).select_related(
        "product", "seller", "order"
    )

    # Get cart count
    cart_count = (
        Cart.objects.filter(customer=request.user).aggregate(total=Sum("quantity"))[
            "total"
        ]
        or 0
    )

    return render(
        request,
        "shop/customer_dashboard.html",
        {"purchases": purchases, "cart_count": cart_count},
    )


@login_required
@require_POST
def add_comment(request, pk):
    """Add a comment to a product."""
    product = get_object_or_404(Product, pk=pk)

    if not Purchase.objects.filter(product=product, customer=request.user).exists():
        raise PermissionDenied("ثبت نظر فقط برای خریداران این محصول مجاز است.")

    if request.method == "POST":
        form = MessageForm(request.POST)
        text = form.cleaned_data["text"] if form.is_valid() else ""
        if text:
            Comment.objects.create(product=product, customer=request.user, text=text)
            messages.success(request, "نظر با موفقیت ثبت شد!")
        else:
            messages.error(request, "نظر باید بین ۱ تا ۲۰۰۰ نویسه باشد.")

    return redirect("product_detail", pk=pk)


@shop_owner_required
def shop_owner_dashboard(request):
    """Shop owner dashboard with products and comments."""
    shop_owner_id = request.session.get("shop_owner_id")

    if not shop_owner_id:
        messages.error(request, "Please log in as a shop owner.")
        return redirect("shop_owner_login")

    try:
        shop_owner = ShopOwner.objects.get(id=shop_owner_id)
    except ShopOwner.DoesNotExist:
        messages.error(request, "Shop owner not found.")
        return redirect("shop_owner_login")

    # Get shop owner's products
    products = Product.objects.filter(shop_owner=shop_owner)

    # Get products sold data
    products_sold = (
        Purchase.objects.filter(seller=shop_owner)
        .select_related("product", "customer", "order")
        .order_by("-created_at")
    )

    # Calculate total products sold
    total_products_sold = (
        Purchase.objects.filter(seller=shop_owner).aggregate(total=Sum("quantity"))[
            "total"
        ]
        or 0
    )

    # Get pending comments (comments without replies)
    pending_comments = (
        Comment.objects.filter(product__shop_owner=shop_owner)
        .exclude(id__in=Reply.objects.values_list("comment_id", flat=True))
        .select_related("product", "customer")
    )

    # Get all comments with replies for this shop owner
    all_comments = (
        Comment.objects.filter(product__shop_owner=shop_owner)
        .select_related("product", "customer")
        .prefetch_related("reply")
    )

    return render(
        request,
        "shop/shop_owner_dashboard.html",
        {
            "shop_owner": shop_owner,
            "products": products,
            "products_sold": products_sold,
            "total_products_sold": total_products_sold,
            "pending_comments": pending_comments,
            "all_comments": all_comments,
        },
    )


@shop_owner_required
def add_product(request):
    """Add a new product (shop owner only)."""
    shop_owner_id = request.session.get("shop_owner_id")

    if not shop_owner_id:
        messages.error(request, "Please log in as a shop owner.")
        return redirect("shop_owner_login")

    try:
        shop_owner = ShopOwner.objects.get(id=shop_owner_id)
    except ShopOwner.DoesNotExist:
        messages.error(request, "Shop owner not found.")
        return redirect("shop_owner_login")

    form = ProductForm(
        request.POST if request.method == "POST" else None, request.FILES or None
    )
    if request.method == "POST":
        if form.is_valid():
            product = form.save(commit=False)
            product.shop_owner = shop_owner
            product.save()
            messages.success(request, "محصول با موفقیت ذخیره شد.")
            return redirect("shop_owner_dashboard")
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return render(request, "shop/add_product.html", {"form": form})


@require_POST
@shop_owner_required
def reply_to_comment(request, comment_id):
    """Reply to a customer comment (shop owner only)."""
    shop_owner_id = request.session.get("shop_owner_id")

    if not shop_owner_id:
        messages.error(request, "Please log in as a shop owner.")
        return redirect("shop_owner_login")

    try:
        shop_owner = ShopOwner.objects.get(id=shop_owner_id)
    except ShopOwner.DoesNotExist:
        messages.error(request, "Shop owner not found.")
        return redirect("shop_owner_login")

    comment = get_object_or_404(Comment, id=comment_id, product__shop_owner=shop_owner)

    if request.method == "POST":
        form = MessageForm(request.POST)
        text = form.cleaned_data["text"] if form.is_valid() else ""
        if text:
            _, created = Reply.objects.get_or_create(
                comment=comment, defaults={"shop_owner": shop_owner, "text": text}
            )
            messages.success(
                request,
                (
                    "پاسخ با موفقیت ثبت شد!"
                    if created
                    else "این نظر قبلاً پاسخ داده شده است."
                ),
            )
        else:
            messages.error(request, "پاسخ باید بین ۱ تا ۲۰۰۰ نویسه باشد.")

    return redirect("shop_owner_dashboard")


@require_POST
@shop_owner_required
@transaction.atomic
def delete_product(request, pk):
    """Delete a product (shop owner only)."""
    shop_owner_id = request.session.get("shop_owner_id")

    if not shop_owner_id:
        messages.error(request, "Please log in as a shop owner.")
        return redirect("shop_owner_login")

    try:
        shop_owner = ShopOwner.objects.get(id=shop_owner_id)
    except ShopOwner.DoesNotExist:
        messages.error(request, "Shop owner not found.")
        return redirect("shop_owner_login")

    product = get_object_or_404(
        Product.objects.select_for_update(), pk=pk, shop_owner=shop_owner
    )
    product.delete()
    messages.success(request, "محصول با موفقیت حذف شد!")

    return redirect("shop_owner_dashboard")


@shop_owner_required
@transaction.atomic
def edit_product(request, pk):
    """Edit an existing product (shop owner only)."""
    shop_owner_id = request.session.get("shop_owner_id")

    if not shop_owner_id:
        messages.error(request, "Please log in as a shop owner.")
        return redirect("shop_owner_login")

    try:
        shop_owner = ShopOwner.objects.get(id=shop_owner_id)
    except ShopOwner.DoesNotExist:
        messages.error(request, "Shop owner not found.")
        return redirect("shop_owner_login")

    product = get_object_or_404(
        Product.objects.select_for_update(), pk=pk, shop_owner=shop_owner
    )

    form = ProductForm(
        request.POST if request.method == "POST" else None,
        request.FILES or None,
        instance=product,
    )
    if request.method == "POST":
        if form.is_valid():
            product = form.save(commit=False)
            product.shop_owner = shop_owner
            product.save()
            messages.success(request, "محصول با موفقیت ذخیره شد.")
            return redirect("shop_owner_dashboard")
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return render(request, "shop/edit_product.html", {"form": form, "product": product})


@shop_owner_required
def product_comments(request, pk):
    """View and reply to comments for a specific product (shop owner only)."""
    shop_owner_id = request.session.get("shop_owner_id")

    if not shop_owner_id:
        messages.error(request, "Please log in as a shop owner.")
        return redirect("shop_owner_login")

    try:
        shop_owner = ShopOwner.objects.get(id=shop_owner_id)
    except ShopOwner.DoesNotExist:
        messages.error(request, "Shop owner not found.")
        return redirect("shop_owner_login")

    product = get_object_or_404(Product, pk=pk, shop_owner=shop_owner)
    comments = product.comments.select_related("customer").prefetch_related("reply")

    return render(
        request,
        "shop/product_comments.html",
        {"product": product, "comments": comments, "shop_owner": shop_owner},
    )


def shop_profile(request, shop_owner_id):
    """Display shop profile with all products from a specific shop."""
    shop_owner = get_object_or_404(ShopOwner, pk=shop_owner_id)
    products = Product.objects.filter(shop_owner=shop_owner)

    return render(
        request,
        "shop/shop_profile.html",
        {"shop_owner": shop_owner, "products": products},
    )
