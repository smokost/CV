from django.urls import (
    path,
    include,
)
app_name = 'restapiapp'
urlpatterns = [
    # path('', include('restapiapp.searchapi.urls', namespace='searchapi')),
    path('', include('restapiapp.categoriesapi.urls', namespace='categoriesapi')),
    path('', include('restapiapp.productsapi.urls', namespace='productsapi')),
    path('', include('restapiapp.reviewapi.urls', namespace='reviewapi')),
    path('', include('restapiapp.featuresapi.urls', namespace='featuresapi')),
]
