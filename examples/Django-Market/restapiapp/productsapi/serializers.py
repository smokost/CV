from rest_framework import serializers

from marketapp.models import (
    Category,
    Product,
    ProductCategoryM2M,
    # ProductFeatureM2M,
)
from restapiapp.categoriesapi.serializers import CategorySerializer
# from restapiapp.featuresapi.serializers import (
#     # FeatureSerializer,
#     # FeatureValuesSerializer,
# )
from utils.serializers import (
    LogoModelSerilizerMixin,
    IsActiveTrueSerializerMixin,
)


# class ProductFeatureM2MSerializer(serializers.ModelSerializer):
#     """Сериалайзер для множественной связи Свойств и Продуктов"""
#     featurevalue = FeatureValuesSerializer(
#         label='Значение свойства продукта',
#         help_text='Значение свойства продукта',
#         read_only=True,
#     )
#
#     class Meta:
#         model = ProductFeatureM2M
#         fields = (
#             # 'feature',
#             'featurevalue',
#         )


class ProductSerializer(
    LogoModelSerilizerMixin,
    IsActiveTrueSerializerMixin,
    serializers.ModelSerializer
):
    """
    Сериалайзер для товара
    """

    user = serializers.CharField(
        source='user.username',
        label='Пользователь',
        help_text='Создатель товара',
        read_only=True,
    )
    # feature_set = ProductFeatureM2MSerializer(
    #     source='productfeaturem2m_set',
    #     read_only=True,
    #     many=True,
    # )

    class Meta:
        model = Product
        fields = (
            'uuid',
            'is_active',
            'name',
            'desc',
            'logo',
            'logo_small',
            'logo_big',
            'logo_large',
            'time_updated',
            'time_created',
            'time_publish',
            'time_depublish',
            'user',
            'price',
            'temporary_price',
            'rating',
            'owner_rating',
            # 'feature_set',
        )


class ProductCategorySerialzer(serializers.ModelSerializer):
    """Сериалайзер для отображения категории в API для продукта"""
    category = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=Category.objects.all(),
        label=ProductCategoryM2M._meta.get_field('category').verbose_name,
        help_text='uuid категории, связанной с продуктом',
    )
    category_detail = CategorySerializer(
        source='category',
        read_only=True,
    )

    class Meta:
        model = ProductCategoryM2M
        fields = (
            'category',
            'category_detail',
        )


class CategoryProductSerialzer(serializers.ModelSerializer):
    """Сериалайзер для отображения продукта в API для категории"""
    product = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=Product.objects.all(),
        label=ProductCategoryM2M._meta.get_field('product').verbose_name,
        help_text='uuid продукта, связанного с категорией',
    )
    product_detail = CategorySerializer(
        source='product',
        read_only=True,
    )

    class Meta:
        model = ProductCategoryM2M
        fields = (
            'product',
            'product_detail',
        )


class ProductCategoryM2MSerializer(ProductCategorySerialzer, CategoryProductSerialzer):
    """
    Сериалайзер для связи Product-Category
    """

    class Meta:
        model = ProductCategoryM2M
        fields = (
            'category',
            'product',
            'category_detail',
            'product_detail',
        )

