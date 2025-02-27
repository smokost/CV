from datetime import timedelta

from django.contrib.auth import get_user_model
from rest_framework import serializers

from marketapp.models import (
    Product,
    Review,
)
from utils.serializers import IsActiveTrueSerializerMixin

User = get_user_model()


class ReviewSerializer(
    IsActiveTrueSerializerMixin,
    serializers.ModelSerializer
):
    """Сериалайзер отзывов на товар"""

    product = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=Product.objects.all(),
        label=Review._meta.get_field('product').verbose_name,
        help_text='uuid продукта, связанного с отзывом',
    )
    user = serializers.CharField(
        source='user.username',
        label='Пользователь',
        help_text='Создатель отзыва',
        read_only=True,
    )
    edited = serializers.SerializerMethodField(
        label='Изменено',
        help_text='Статус изменения отзыва',
        method_name='get_edited',
        read_only=True,
    )

    def get_edited(self, obj):
        return obj.time_updated > obj.time_created + timedelta(seconds=1)

    answer_to = serializers.SlugRelatedField(
        slug_field='uuid',
        queryset=Review.objects.all(),
        label=Review._meta.get_field('answer_to').verbose_name,
        help_text='uuid отзыва/комментария, на который дается ответ',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Review
        fields = (
            'uuid',
            'is_active',
            'rating',
            'text',
            'product',
            'user',
            'time_created',
            'time_updated',
            'edited',
            'type',
            'answer_to',
        )


# class CommentSerializer(
#     IsActiveTrueSerializerMixin,
#     serializers.ModelSerializer
# ):
#     """Сериалайзер комментариев на товар"""
#
#     product = serializers.SlugRelatedField(
#         slug_field='uuid',
#         queryset=Product.objects.all(),
#         label=Review._meta.get_field('product').verbose_name,
#         help_text='uuid продукта, связанного с комментарием',
#     )
#     user = serializers.CharField(
#         source='user.username',
#         label='Пользователь',
#         help_text='Создатель комментария',
#         read_only=True,
#     )
#     edited = serializers.SerializerMethodField(
#         label='Изменено',
#         help_text='Статус изменения комментария',
#         method_name='get_edited',
#         read_only=True,
#     )
#     answer_to = serializers.SlugRelatedField(
#         slug_field='uuid',
#         queryset=Comment.objects.all(),
#         label=Comment._meta.get_field('answer_to').verbose_name,
#         help_text='uuid комментария, на который дается ответ',
#     )
#
#     def get_edited(self, obj):
#         return obj.time_updated > obj.time_created + timedelta(seconds=1)
#
#     class Meta:
#         model = Comment
#         fields = (
#             'uuid',
#             'is_active',
#             'text',
#             'product',
#             'user',
#             'time_created',
#             'time_updated',
#             'edited',
#             'answer_to',
#         )
