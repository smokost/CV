from rest_framework import (
    viewsets,
    mixins,
    permissions,
)
from marketapp.models import (
    Feature,
)
from restapiapp.featuresapi.filters import FeaturesFilter
from restapiapp.featuresapi.helpers import (
    filter_feature_by_category_uuid,
    filter_feature_by_product_uuid,
)
from restapiapp.featuresapi.serializers import (
    CategoryFeaturesSerializer,
)
# from utils.api import BulkDestroyMixin
# from utils.permissions import ReadOnlyOrAdminPermission


# class FeatureValuesApiViewSet(BulkDestroyMixin, viewsets.ModelViewSet):
#     """
#     API для значений свойства продуктов категории.
#
#     list: Список доступных свойств всех продуктов. Доступно всем
#     retrieve: Детальная свойства. Доступно всем.
#     create: Создание свойства. Доступно только администратору.
#     update: Обновление свойства. Доступно только администратору.
#     partial_update: Частичное обновление свойства. Доступно только администратору.
#     destroy: Удаление свойства. Доступно только администратору.
#     bulk_destroy: Удаление свойств по фильтру. Доступно только администратору.
#     """
#
#     queryset = FeatureValue.objects.order_by('feature__id', 'id')
#     serializer_class = FeatureValuesSerializer
#     permission_classes = (
#         ReadOnlyOrAdminPermission,
#     )
#     filterset_class = FeaturesValuesFilter


class CategoryFeaturesApiViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API для списка свойств, относящихся к категории или продукту
    """

    queryset = Feature.objects.all()
    serializer_class = CategoryFeaturesSerializer
    permission_classes = (
        permissions.AllowAny,
    )
    filterset_class = FeaturesFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = filter_feature_by_category_uuid(queryset, prefix='featurevalue__',  **self.kwargs)
        queryset = filter_feature_by_product_uuid(queryset, prefix='featurevalue__', **self.kwargs)
        return queryset.distinct()
