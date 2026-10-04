from accounts.middleware import shop_owner_required
from accounts.models import ShopOwner
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ProductForm
from .models import Cart, Comment, Product, Purchase, Reply


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
    """Add product to cart."""
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        try:
            quantity = int(request.POST.get("quantity", 1))
        except ValueError:
            quantity = 1

        # Validate quantity (max 5)
        if quantity < 1:
            quantity = 1
        elif quantity > 5:
            quantity = 5
            messages.warning(request, "Maximum 5 units per product allowed.")

        # Check stock availability
        if not product.is_in_stock():
            messages.error(request, f"{product.name} ناموجود است.")
            return redirect("product_detail", pk=pk)

        if not product.has_enough_stock(quantity):
            messages.error(
                request, f"فقط {product.stock} عدد از {product.name} موجود است."
            )
            return redirect("product_detail", pk=pk)

        # Check if product already in cart
        cart_item, created = Cart.objects.get_or_create(
            customer=request.user, product=product, defaults={"quantity": quantity}
        )

        if not created:
            # Product already in cart, update quantity
            new_quantity = cart_item.quantity + quantity
            if new_quantity > 5:
                new_quantity = 5
                messages.warning(request, "حداکثر ۵ عدد از هر محصول مجاز است.")
            cart_item.quantity = new_quantity
            cart_item.save()
            messages.success(
                request, f"تعداد {product.name} در سبد خرید به‌روزرسانی شد."
            )
        else:
            messages.success(request, f"{product.name} به سبد خرید اضافه شد.")

    return redirect("product_detail", pk=pk)


@login_required
def view_cart(request):
    """Display shopping cart."""
    cart_items = Cart.objects.filter(customer=request.user).select_related("product")

    # Calculate totals
    total_items = cart_items.aggregate(total=Sum("quantity"))["total"] or 0
    total_price = sum(item.get_total_price() for item in cart_items)

    return render(
        request,
        "shop/cart.html",
        {
            "cart_items": cart_items,
            "total_items": total_items,
            "total_price": total_price,
        },
    )


@login_required
@require_POST
def update_cart(request, pk):
    """Update cart item quantity."""
    cart_item = get_object_or_404(Cart, pk=pk, customer=request.user)

    if request.method == "POST":
        try:
            quantity = int(request.POST.get("quantity", 1))
        except ValueError:
            quantity = 1

        # Validate quantity (max 5)
        if quantity < 1:
            quantity = 1
        elif quantity > 5:
            quantity = 5
            messages.warning(request, "Maximum 5 units per product allowed.")

        # Check stock availability
        if not cart_item.product.has_enough_stock(quantity):
            messages.error(request, f"فقط {cart_item.product.stock} عدد موجود است.")
            return redirect("view_cart")

        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, "سبد خرید با موفقیت به‌روزرسانی شد.")

    return redirect("view_cart")


@login_required
@require_POST
def remove_from_cart(request, pk):
    """Remove item from cart."""
    cart_item = get_object_or_404(Cart, pk=pk, customer=request.user)
    cart_item.delete()
    messages.success(request, "مورد از سبد خرید حذف شد.")
    return redirect("view_cart")


@login_required
@transaction.atomic
@require_POST
def checkout(request):
    """Process checkout and deduct inventory."""
    cart_items = Cart.objects.filter(customer=request.user).select_related("product")

    if not cart_items.exists():
        messages.error(request, "سبد خرید شما خالی است.")
        return redirect("view_cart")

    # Validate stock availability for all items
    for item in cart_items:
        if not item.product.has_enough_stock(item.quantity):
            messages.error(
                request,
                f"موجودی کافی برای {item.product.name} نیست. فقط {item.product.stock} عدد موجود است.",
            )
            return redirect("view_cart")

    # Process purchases and deduct inventory
    total_purchase_price = 0
    for item in cart_items:
        # Deduct stock
        item.product.stock -= item.quantity
        item.product.save()

        # Create purchase record
        purchase_price = item.product.price * item.quantity
        Purchase.objects.create(
            product=item.product,
            customer=request.user,
            quantity=item.quantity,
            total_price=purchase_price,
        )
        total_purchase_price += purchase_price

    # Clear cart
    cart_items.delete()

    messages.success(
        request, f"سفارش با موفقیت ثبت شد! جمع کل: {total_purchase_price:,.0f} ریال"
    )
    return redirect("customer_dashboard")


@login_required
def customer_dashboard(request):
    """Customer dashboard with purchases and browsing."""
    purchases = Purchase.objects.filter(customer=request.user).select_related(
        "product", "product__shop_owner"
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
        return HttpResponseForbidden("ثبت نظر فقط برای خریداران این محصول مجاز است.")

    if request.method == "POST":
        text = request.POST.get("text")
        if text:
            Comment.objects.create(product=product, customer=request.user, text=text)
            messages.success(request, "نظر با موفقیت ثبت شد!")
        else:
            messages.error(request, "نظر نمی‌تواند خالی باشد.")

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
        Purchase.objects.filter(product__shop_owner=shop_owner)
        .select_related("product", "customer")
        .order_by("-created_at")
    )

    # Calculate total products sold
    total_products_sold = (
        Purchase.objects.filter(product__shop_owner=shop_owner).aggregate(
            total=Sum("quantity")
        )["total"]
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
        text = request.POST.get("text")
        if text:
            Reply.objects.create(comment=comment, shop_owner=shop_owner, text=text)
            messages.success(request, "پاسخ با موفقیت ثبت شد!")
        else:
            messages.error(request, "پاسخ نمی‌تواند خالی باشد.")

    return redirect("shop_owner_dashboard")


@require_POST
@shop_owner_required
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

    product = get_object_or_404(Product, pk=pk, shop_owner=shop_owner)
    product.delete()
    messages.success(request, "محصول با موفقیت حذف شد!")

    return redirect("shop_owner_dashboard")


@shop_owner_required
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

    product = get_object_or_404(Product, pk=pk, shop_owner=shop_owner)

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
