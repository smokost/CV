from rest_framework import serializers

from marketapp.models import (
    Category,
)
from utils.serializers import (
    LogoModelSerilizerMixin,
    IsActiveTrueSerializerMixin,
)


class CategorySerializer(
    LogoModelSerilizerMixin,
    IsActiveTrueSerializerMixin,
    serializers.ModelSerializer
):
    """
    Сериалайзер для категорий
    """
    parent = serializers.SlugRelatedField(
        slug_field='uuid',
        allow_null=True,
        required=False,
        default=None,
        queryset=Category.objects.all(),
        label=Category._meta.get_field('parent').verbose_name,
        help_text=Category._meta.get_field('parent').help_text,
    )

    class Meta:
        model = Category
        fields = (
            'uuid',
            'is_active',
            'name',
            'desc',
            'parent',
            'logo',
            'logo_small',
            'logo_big',
            'logo_large',
            'sort',
        )
