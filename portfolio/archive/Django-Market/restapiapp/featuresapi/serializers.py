from django.db import models
from rest_framework import serializers

from marketapp.models import (
    Feature,
    FeatureValue,
)
from restapiapp.featuresapi.helpers import (
    filter_feature_by_category_uuid,
    filter_feature_by_product_uuid,
)


# class FeatureSerializer(serializers.ModelSerializer):
#     """Сериалайзер для Свойства Продукта"""
#
#     class Meta:
#         model = Feature
#         fields = (
#             '__all__'
#         )


# class FeatureValuesSerializer(serializers.ModelSerializer):
#     """Сериалайзер для Значения Свойства Продукта"""
#     feature = FeatureSerializer(
#         label='Свойство продукта',
#         help_text='Свойство продукта',
#         read_only=True,
#     )
#
#     class Meta:
#         model = FeatureValue
#         fields = '__all__'


class CategoryFeatureValueSetListSerializer(serializers.ListSerializer):
    """
    Лист-сериалайзер значений свойства с фильтрацией
    внутри вложенного сериалайзера по категории продукта
    и по самому продукту

    view.kwargs должен содержать category_uuid и product_uuid
    """
    def to_representation(self, data):
        # super().to_representation(data)
        iterable = data.all() if isinstance(data, models.Manager) else data
        view = self.context.get('view', None)
        if view and view.kwargs:
            iterable = filter_feature_by_category_uuid(iterable, **view.kwargs)
            iterable = filter_feature_by_product_uuid(iterable, **view.kwargs)
            iterable = iterable.distinct()
        return [
            self.child.to_representation(item) for item in iterable
        ]


class CategoryFeatureValueSetSerializer(serializers.ModelSerializer):
    """
    Сериалайзер значений свойства продукта
    """

    class Meta:
        list_serializer_class = CategoryFeatureValueSetListSerializer
        model = FeatureValue
        fields = (
            'id',
            'uuid',
            'name',
            'desc',
        )


class CategoryFeaturesSerializer(serializers.ModelSerializer):
    """Сериалайзер свойств продукта"""

    featurevalue_set = CategoryFeatureValueSetSerializer(
        label='Список значений свойства',
        help_text='Значения свойства для конкретного объекта',
        many=True,
        read_only=True,
    )

    class Meta:
        model = Feature
        fields = (
            'id',
            'uuid',
            'is_active',
            'name',
            'desc',
            'featurevalue_set',
        )
