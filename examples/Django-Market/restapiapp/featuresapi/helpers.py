from django.core.exceptions import ValidationError


def filter_feature_factory(queryset, queryset_filter, uuid):
    """Фильтрация свойств"""
    if uuid:
        fltr = {queryset_filter: uuid}
        try:
            queryset = queryset.filter(**fltr)
        except ValidationError as err:
            # pass
            queryset = queryset.none()
    return queryset


def filter_feature_by_category_uuid(queryset, category__uuid=None, prefix='', **kwargs):
    """Фильтрация свойств по категории"""
    return filter_feature_factory(
        queryset,
        prefix + 'productfeaturem2m__product__productcategorym2m__category__uuid',
        category__uuid,
    )


def filter_feature_by_product_uuid(queryset, product__uuid=None, prefix='', **kwargs):
    """Фильтрация свойств по продукту"""
    return filter_feature_factory(
        queryset,
        prefix + 'productfeaturem2m__product__uuid',
        product__uuid,
    )
