from django.urls import (
    path,
)

from restapiapp.productsapi.api import (
    ProductsAPIViewSet,
    ProductCategoryAPIView,
)

app_name = 'categoriesapi'
urlpatterns = [
    # Товары
    path(
        'v1/products/',
        ProductsAPIViewSet.as_view({
            'get': 'list',
            'post': 'create',
            # 'delete': 'bulk_destroy',
        }),
        name='products'
    ),
    path(
        'v1/products/<str:uuid>/',
        ProductsAPIViewSet.as_view({
            'get': 'retrieve',
            'delete': 'save_destroy',
            'put': 'update',
            'patch': 'partial_update',
        }),
        name='product'
    ),
    path(
        'v1/products/<str:product__uuid>/categories/',
        ProductCategoryAPIView.as_view({
            'get': 'list',
            'post': 'create',
            'delete': 'destroy',
        }),
        name='product_categories'
    ),
    path(
        'v1/products/<str:product__uuid>/categories/<str:category__uuid>/',
        ProductCategoryAPIView.as_view({
            'get': 'retrieve',
            'delete': 'destroy',
        }),
        name='product_category'
    ),
]
