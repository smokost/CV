import django_filters

from marketapp.models import Review
from utils.filters import (
    IsActiveFilterMixin,
    UuidOrNameFilterMethodMixin,
    TimeRangeFilterMixin,
)


class ReviewFilter(
    IsActiveFilterMixin,
    UuidOrNameFilterMethodMixin,
    TimeRangeFilterMixin,
    django_filters.FilterSet,
):
    """Фильтры для API отзывов на товар"""

    order = django_filters.OrderingFilter(
        fields=(
            ('rating', 'rating'),
            ('time_created', 'time_created'),
            ('product', 'product'),
            ('user', 'user'),
        ),
        field_labels={
            'rating': 'Рейтин отзыва',
            'time_created': 'Время создания отзыва',
            'product': 'Продукты отзыва',
            'user': 'Пользователь отзыва',
        },
        label='Сортировка',
        help_text='Сортировка отзывов: rating, time_created, product, user',
    )
    rating = django_filters.NumberFilter(
        label='Рейтинг',
        help_text='Фильтрация по рейтингу отзывов',
    )
    product = django_filters.CharFilter(
        label=Review._meta.get_field('product').verbose_name,
        help_text='Поиск по uuid или имени продукта. Можно использовать regex.',
        field_name='product',
        method='filter_by_uuid_or_name',
    )
    category = django_filters.CharFilter(
        label='Категория продукта отзыва',
        help_text='Поиск по uuid или имени категории. Можно использовать regex.',
        field_name='product__productcategorym2m__category',
        method='filter_by_uuid_or_name',
    )
    user = django_filters.CharFilter(
        label=Review._meta.get_field('user').verbose_name,
        help_text='Фильтр отзывов по username создателя отзыва',
        field_name='user__username',
    )
    type = django_filters.ChoiceFilter(
        label=Review._meta.get_field('type').verbose_name,
        help_text='Фильтр по типу. ' + Review._meta.get_field('type').help_text,
        choices=Review.TYPE_CHOICES,
    )
    answer_to = django_filters.ModelChoiceFilter(
        label=Review._meta.get_field('answer_to').verbose_name,
        help_text='Фильтр по ответному комментарию. ' + Review._meta.get_field('answer_to').help_text,
        queryset=Review.objects.all(),
        to_field_name='uuid',
    )


# class CommentFilter(
#     IsActiveFilterMixin,
#     UuidOrNameFilterMethodMixin,
#     TimeRangeFilterMixin,
#     django_filters.FilterSet,
# ):
#     """Фильтры для API комментариев на товар"""
#
#     order = django_filters.OrderingFilter(
#         fields=(
#             ('time_created', 'time_created'),
#             ('product', 'product'),
#             ('user', 'user'),
#             ('answer_to', 'answer_to'),
#         ),
#         field_labels={
#             'time_created': 'Время создания отзыва',
#             'product': 'Продукты отзыва',
#             'user': 'Пользователь отзыва',
#             'answer_to': 'Комментарий ответа',
#         },
#         label='Сортировка',
#         help_text='Сортировка отзывов: time_created, product, user, answer_to',
#     )
#     product = django_filters.CharFilter(
#         label=Comment._meta.get_field('product').verbose_name,
#         help_text='Поиск по uuid или имени продукта. Можно использовать regex.',
#         field_name='product',
#         method='filter_by_uuid_or_name',
#     )
#     category = django_filters.CharFilter(
#         label='Категория продукта комментария',
#         help_text='Поиск по uuid или имени категории. Можно использовать regex.',
#         field_name='product__productcategorym2m__category',
#         method='filter_by_uuid_or_name',
#     )
#     user = django_filters.CharFilter(
#         label='Пользователь',
#         help_text='Фильтр комментариев по username создателя отзыва',
#         field_name='user__username',
#     )


