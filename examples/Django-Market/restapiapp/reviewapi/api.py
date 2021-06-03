from rest_framework import (
    viewsets,
    exceptions,
)

from marketapp.models import (
    Review,
)
from restapiapp.reviewapi.filters import (
    ReviewFilter,
)
from restapiapp.reviewapi.serializers import (
    ReviewSerializer,
)
from utils.api import SaveDestroyMixin
from utils.permissions import ReadOnlyOrOwnerPermission


class ReviewAPIViewSet(
    SaveDestroyMixin,
    viewsets.ModelViewSet,
):
    """
    API для отзывов на товар

    list: Список отзывов. Доступно всем.
    retrieve: Детальная отзыва. Доступно всем.
    create: Создание отзыва на товар. Доступно авторизованному.
    update: Обновление отзыва на товар. Доступно создателю и админу.
    partial_update: Частичное обновление отзыва на товар. Доступно создателю и админу.
    save_destroy: "Безопасное" удаление отзыва. Доступно создателю и админу.
    """

    queryset = Review.objects.all()
    lookup_field = 'uuid'
    serializer_class = ReviewSerializer
    permission_classes = [
        ReadOnlyOrOwnerPermission
    ]
    filterset_class = ReviewFilter

    def perform_create(self, serializer: ReviewSerializer):
        """Пользовтаель не может оставить комментарий или оценку своему же товару"""
        product = serializer.validated_data['product']
        if not self.request.user.is_staff and product.user == self.request.user:
            raise exceptions.PermissionDenied
        serializer.save(user=self.request.user)


# class CommentAPIViewSet(
#     SaveDestroyMixin,
#     viewsets.ModelViewSet,
# ):
#     """
#     API для комментариев на товар
#
#     list: Список комментариев. Доступно всем.
#     retrieve: Детальная комментария. Доступно всем.
#     create: Создание комментария на товар. Доступно авторизованному.
#     update: Обновление комментария на товар. Доступно создателю и админу.
#     partial_update: Частичное обновление комментария на товар. Доступно создателю и админу.
#     save_destroy: "Безопасное" удаление комменатрия. Доступно создателю и админу.
#     """
#
#     queryset = Review.objects.all()
#     lookup_field = 'uuid'
#     serializer_class = CommentSerializer
#     permission_classes = [
#         ReadOnlyOrOwnerPermission
#     ]
#     filterset_class = CommentFilter
#
#     def perform_create(self, serializer):
#         serializer.save(user=self.request.user)
