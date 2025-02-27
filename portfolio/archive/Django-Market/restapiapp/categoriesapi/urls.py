from django.urls import (
    path,
)

from restapiapp.categoriesapi.api import (
    CategoriesAPIViewSet,
)

app_name = 'categoriesapi'
urlpatterns = [
    # Категории
    path(
        'v1/categories/',
        CategoriesAPIViewSet.as_view({
            'get': 'list',
            'post': 'create',
            'delete': 'destroy',
        }),
        name='categories'
    ),
    path(
        'v1/categories/<str:uuid>/',
        CategoriesAPIViewSet.as_view({
            'get': 'retrieve',
            'delete': 'destroy',
            'put': 'update',
            'patch': 'partial_update',
        }),
        name='category'
    ),
]
