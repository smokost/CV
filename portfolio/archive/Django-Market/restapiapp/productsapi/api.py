from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import (
    viewsets,
)
from rest_framework.compat import (
    coreapi,
    coreschema,
)
from rest_framework.schemas import AutoSchema

from marketapp.models import (
    Product,
    ProductCategoryM2M,
)
from restapiapp.productsapi.filters import (
    ProductFilter,
)
from restapiapp.productsapi.serializers import (
    ProductSerializer,
    ProductCategoryM2MSerializer,
    ProductCategorySerialzer,
    CategoryProductSerialzer,
)
from utils.api import (
    BulkDestroyMixin,
    SaveDestroyMixin,
)
from utils.permissions import (
    ReadOnlyOrOwnerPermission,
)


class ProductsAPIViewSet(
    # BulkDestroyMixin,
    SaveDestroyMixin,
    viewsets.ModelViewSet
):
    """
    API для товаров

    list: Список товаров. Доступно всем.
    retrieve: Детальная товара. Доступно всем.
    create: Создание товара. Доступно администратору или создателю.
    update: Обновление товара. Доступно администратору или создателю.
    partial_update: Частичное обновление товара. Доступно администратору или создателю.
    """

    queryset = Product.objects.all().order_by('-time_created')
    lookup_field = 'uuid'
    serializer_class = ProductSerializer
    permission_classes = [
        ReadOnlyOrOwnerPermission
    ]
    filterset_class = ProductFilter

    def get_queryset(self):
        now = timezone.now()
        queryset = super().get_queryset().filter(
            Q(
                time_publish__lte=now,
                time_depublish__gte=now,
            )
            |
            Q(
                time_publish__isnull=True,
                time_depublish__isnull=True,
            )
        )
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProductCategoryAPIView(BulkDestroyMixin, viewsets.ModelViewSet):
    """API для связи Product-Category.
    С помощью этой API можно добавлять товар в категорию.
    Или категорию в товар.

    list: Список категорий товара. Доступно всем.
    retrieve: Детальная категории из списка категорий товара. Доступно всем.
    create: Добавление категории в список категорий товара. Доступно администратору или создателю товара.
    delete: Частичное удаление катеории из списка категорий товара. Доступно администратору или создателю товара.
    """

    schema = AutoSchema(
        manual_fields=(
            coreapi.Field(
                name='product__uuid',
                location='path',
                required=True,
                schema=coreschema.String(description='uuid продукта'),
                description='uuid продукта',
            ),
            coreapi.Field(
                name='category__uuid',
                location='path',
                required=True,
                schema=coreschema.String(description='uuid категории'),
                description='uuid категории',
            ),
        )
    )

    lookup_field = 'category__uuid'
    queryset = ProductCategoryM2M.objects.all()
    serializer_class = ProductCategoryM2MSerializer
    permission_classes = [
        ReadOnlyOrOwnerPermission
    ]

    def get_queryset(self):
        queryset = super().get_queryset()
        try:
            queryset = queryset.filter(**self.kwargs)
        except ValidationError as err:
            queryset = queryset.none()

        return queryset

    def perform_create(self, serializer):
        serializer = ProductCategoryM2MSerializer(data=serializer.data)
        if 'category__uuid' in self.kwargs:
            serializer.initial_data['category'] = self.kwargs['category__uuid']
        if 'product__uuid' in self.kwargs:
            serializer.initial_data['product'] = self.kwargs['product__uuid']
        serializer.is_valid(raise_exception=True)
        self.check_object_permissions(self.request, serializer.validated_data['product'])
        serializer.save()

    def get_serializer_class(self):
        serializer_class = super().get_serializer_class()
        if 'category__uuid' in self.kwargs and 'product__uuid' in self.kwargs:
            return serializer_class
        elif 'category__uuid' in self.kwargs:
            return CategoryProductSerialzer
        elif 'product__uuid' in self.kwargs:
            return ProductCategorySerialzer
        return serializer_class
