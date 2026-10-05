from django.urls import path

from . import views

urlpatterns = [
    path("orders/<uuid:number>/", views.order_detail, name="order_detail"),
    path("", views.product_list, name="product_list"),
    path("shop/<int:shop_owner_id>/", views.shop_profile, name="shop_profile"),
    path("product/<int:pk>/", views.product_detail, name="product_detail"),
    path("product/<int:pk>/add-to-cart/", views.add_to_cart, name="add_to_cart"),
    path("product/<int:pk>/comment/", views.add_comment, name="add_comment"),
    path("cart/", views.view_cart, name="view_cart"),
    path("cart/update/<int:pk>/", views.update_cart, name="update_cart"),
    path("cart/remove/<int:pk>/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/checkout/", views.checkout, name="checkout"),
    path("dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("owner/dashboard/", views.shop_owner_dashboard, name="shop_owner_dashboard"),
    path("owner/product/add/", views.add_product, name="add_product"),
    path("owner/product/<int:pk>/edit/", views.edit_product, name="edit_product"),
    path(
        "owner/product/<int:pk>/comments/",
        views.product_comments,
        name="product_comments",
    ),
    path(
        "owner/comment/<int:comment_id>/reply/",
        views.reply_to_comment,
        name="reply_to_comment",
    ),
    path("owner/product/<int:pk>/delete/", views.delete_product, name="delete_product"),
]
