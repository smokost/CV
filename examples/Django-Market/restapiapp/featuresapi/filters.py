import django_filters

# from marketapp.models import (
#     FeatureValue,
#     Feature,
# )
from utils.filters import UuidOrNameFilterMethodMixin


class FeaturesFilter(
    UuidOrNameFilterMethodMixin,
    django_filters.FilterSet,
):
    """Класс с фильтрами для свойств"""

    order = django_filters.OrderingFilter(
        fields=(
            ('id', 'id'),
            ('name', 'name'),
        ),
        field_labels={
            'id': 'Идентификатор свойства',
            'name': 'Значение свойства',
        },
        label='Сортировка',
        help_text='Сортировка свойств: id, name',
    )

    featurevalue = django_filters.CharFilter(
        label='Значение свойства',
        help_text='Поиск по uuid или имени значения свойства. Можно использовать regex.',
        field_name='featurevalue',
        method='filter_by_uuid_or_name',
    )

    category = django_filters.CharFilter(
        label='Катеория продуктов',
        help_text='Поиск по uuid или имени категории продукта. Можно использовать regex.',
        field_name='productfeaturem2m__product__productcategorym2m__category',
        method='filter_by_uuid_or_name',
    )

    product = django_filters.CharFilter(
        label='Продукт',
        help_text='Поиск по uuid или имени продукта. Можно использовать regex.',
        field_name='productfeaturem2m__product',
        method='filter_by_uuid_or_name',
    )
