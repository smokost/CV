import django_filters

from marketapp.models import Category
from utils.filters import (
    IsActiveFilterMixin,
    UuidOrNameFilterMethodMixin,
    NameFilterMixin,
)


class CategoryFilter(
    IsActiveFilterMixin,
    UuidOrNameFilterMethodMixin,
    NameFilterMixin,
    django_filters.FilterSet,
):
    """
    Фильтры для категорий

    is_active
    order
    parent
    name
    product
    user
    """

    order = django_filters.OrderingFilter(
        fields=(
            ('sort', 'sort'),
            ('name', 'name'),
            ('parent', 'parent'),
        ),
        field_labels={
            'sort': 'Параметр сортировки',
            'name': 'Имя категории',
            'parent': 'Родительская категория',
        },
        label='Сортировка',
        help_text='Сортировка категорий: sort, name, parent',
    )

    parent = django_filters.CharFilter(
        label=Category._meta.get_field('parent').verbose_name,
        help_text='Поиск по uuid или имени родительской категории. Можно использовать regex.',
        field_name='parent',
        method='filter_by_uuid_or_name',
    )

    product = django_filters.CharFilter(
        label='Продукт категории',
        help_text='Поиск по uuid или имени продукта. Можно использовать regex.',
        field_name='productcategorym2m__product',
        method='filter_by_uuid_or_name',
    )

    user = django_filters.CharFilter(
        label='Пользователь',
        help_text='Фильтр категорий по username создателя товара',
        field_name='productcategorym2m__product__user__username',
    )
