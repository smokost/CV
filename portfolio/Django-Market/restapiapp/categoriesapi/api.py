from rest_framework import (
    viewsets,
)

from marketapp.models import (
    Category,
)
from restapiapp.categoriesapi.filters import (
    CategoryFilter,
)
from restapiapp.categoriesapi.serializers import (
    CategorySerializer,
)
from utils.api import (
    BulkDestroyMixin,
)
from utils.permissions import (
    ReadOnlyOrAdminPermission,
)


class CategoriesAPIViewSet(BulkDestroyMixin, viewsets.ModelViewSet):
    """
    API для категорий

    list: Список категорий. Доступно всем.
    retrieve: Детальная категории. Доступно всем.
    create: Создание категории. Доступно только администратору.
    update: Обновление категории. Доступно только администратору.
    partial_update: Частичное обновление категории. Доступно только администратору.
    delete: Удаление категории. Доступно только администратору.
    bulk_delete: Удаление категорий по фильтру. Доступно только администратору.
    """

    queryset = Category.objects.all()
    lookup_field = 'uuid'
    serializer_class = CategorySerializer
    permission_classes = (
        ReadOnlyOrAdminPermission,
    )
    filterset_class = CategoryFilter
