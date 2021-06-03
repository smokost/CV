from django.urls import (
    path,
)

from restapiapp.reviewapi.api import ReviewAPIViewSet

app_name = 'reviewapi'
urlpatterns = [
    # Отзывы
    path(
        'v1/reviews/',
        ReviewAPIViewSet.as_view({
            'get': 'list',
            'post': 'create',
        }),
        name='reviews',
    ),
    path(
        'v1/reviews/<str:uuid>/',
        ReviewAPIViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'save_destroy',
        }),
        name='review',
    )
]
