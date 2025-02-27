import django_filters

from marketapp.models import Product
from utils.filters import (
    IsActiveFilterMixin,
    UuidOrNameFilterMethodMixin,
    TimeRangeFilterMixin,
    NameFilterMixin,
    RatingFilterMixin,
)


class ProductFilter(
    IsActiveFilterMixin,
    UuidOrNameFilterMethodMixin,
    TimeRangeFilterMixin,
    NameFilterMixin,
    RatingFilterMixin,
    django_filters.FilterSet
):
    """
    Фильтры для Товара

    is_active
    order
    category
    name
    user
    """

    order = django_filters.OrderingFilter(
        fields=(
            ('name', 'name'),
            ('rating', 'rating'),
            ('time_updated', 'time_updated'),
            ('time_created', 'time_created'),
        ),
        field_labels={
            'name': 'Имя товара',
            'rating': 'Рейтинг товара',
            'time_updated': 'Время обновления',
            'time_created': 'Время создания',
        },
        label='Сортировка',
        help_text='Сортировка Товара: name, rating, time_updated, time_created',
    )

    category = django_filters.CharFilter(
        label=Product._meta.get_field('category_set').verbose_name,
        help_text='Поиск по uuid или имени категории. Можно использовать regex.',
        field_name='productcategorym2m__category',
        method='filter_by_uuid_or_name',
    )

    user = django_filters.CharFilter(
        label='Пользователь',
        help_text='Фильтр товаров по username создателя товара',
        field_name='user__username',
    )

    price = django_filters.RangeFilter(
        field_name='price',
        label='Фильтр по цене',
        help_text='Фильтр по цене. Суффиксы _min и _max',
    )

    feature_ex = django_filters.BaseCSVFilter(
        label='Исключающий фильтр по свойствам',
        help_text='Исключает продукты, в которых нет указанных в фильтре свойств',
        field_name='productfeaturem2m',
        lookup_expr='featurevalue__id__in',
        exclude=True,
    )
