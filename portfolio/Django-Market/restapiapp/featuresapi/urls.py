from django.urls import (
    path,
)

from restapiapp.featuresapi.api import (
    # FeatureValuesApiViewSet,
    CategoryFeaturesApiViewSet,
)

app_name = 'featuresapi'
urlpatterns = [
    # path(
    #     'v1/features/',
    #     FeatureValuesApiViewSet.as_view({
    #         'get': 'list',
    #         # 'post': 'create',
    #         # 'delete': 'destroy',
    #     }),
    #     name='category-features',
    # ),
    # path(
    #     'v1/features/<str:uuid>/',
    #     FeaturesApiViewSet.as_view({
    #         'get': 'retrieve',
    #         'put': 'update',
    #         'patch': 'partial_update',
    #         'delete': 'destroy',
    #     }),
    #     name='category-features',
    # ),
    path(
        'v1/categories/<str:category__uuid>/features/',
        CategoryFeaturesApiViewSet.as_view({
            'get': 'list',
        }),
        name='category-features',
    ),
    path(
        'v1/products/<str:product__uuid>/features/',
        CategoryFeaturesApiViewSet.as_view({
            'get': 'list',
        }),
        name='product-features',
    ),
]
