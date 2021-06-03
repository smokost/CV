# from random import randint
# import time

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from marketapp.models import (
    Category,
    Product,
    Review,
)
from restapiapp.reviewapi.serializers import ReviewSerializer
from utils.tests import (
    BaseModelAPITestCaseMixin,
    # BaseAPITestCaseMixin,
)

User = get_user_model()


class TestReviewsAPI(BaseModelAPITestCaseMixin, APITestCase):
    """
    Класс для тестирования API отзывов на продукты
    """

    serializer_class = ReviewSerializer
    model_class = Review
    instance_detail_keys = [
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
    ]
    api_list_urn = '/api/v1/reviews/'
    api_create_urn = api_list_urn
    api_detail_urn = '/api/v1/reviews/{}/'
    api_update_urn = api_detail_urn
    api_delete_urn = api_detail_urn
    api_bulk_delete_urn = api_list_urn

    @classmethod
    def setUpTestData(cls):
        cls.user_admin = cls.create_admin()

        # Создаем пачку категорий
        Category.objects.bulk_create([
            Category(name=f'cat{i}') for i in range(0, 10)
        ])

        # Создаем пачку продуктов в одной категории
        cls.category_parent1 = Category.objects.filter(is_active=True).first()
        products = Product.objects.bulk_create([
            Product(name=f'cat{i}', user=cls.user_admin) for i in range(0, 10)
        ])
        cls.product = products[0]
        for product in products:
            product.category_set.add(cls.category_parent1)

        cls.user1 = User.objects.create(
            username='testuser',
        )
        cls.user2 = User.objects.create(
            username='testuser2',
        )

        # Создаем отзывы на товар
        cls.review1 = Review.objects.create(
            product=cls.product,
            user=cls.user1,
        )

        cls.review_to_delete = Review.objects.create(
            text='product_to_delete',
            product=cls.product,
            user=cls.user1,
        )

    def test_api_get_list_admin(self):
        """Тест запроса списка объектов админом"""
        self.get_api_list_test('admin')
        self.get_api_list_test('admin', {'is_active': True})
        self.get_api_list_test('admin', {'is_active': False})

    def test_api_get_list_not_admin(self):
        """Тест запроса списка объектов уктов не админом"""
        self.get_api_list_test('testuser')
        self.get_api_list_test('testuser', {'is_active': True})
        self.get_api_list_test('testuser', {'is_active': False})

    def test_api_get_list_anonymous(self):
        """Тест запроса списка объектов анонимным"""
        self.get_api_list_test(None)
        self.get_api_list_test(None, {'is_active': True})
        self.get_api_list_test(None, {'is_active': False})

    def test_api_get_list_search_by_category_uuid(self):
        """Тест запроса списка объектов. Поиск по uuid категории"""
        query = {'category': self.category_parent1.uuid}
        query_filter = {'product__productcategorym2m__category__uuid': self.category_parent1.uuid}
        self.get_api_list_test(None, query, query_filter)

    def test_api_get_list_search_by_category_name(self):
        """Тест запроса списка объектов. Поиск по имени категории"""
        query = {'category': self.category_parent1.name}
        query_filter = {'product__productcategorym2m__category__name': self.category_parent1.name}
        self.get_api_list_test(None, query, query_filter)

    def test_api_create_authorized(self):
        """Тест создания нового объекта. Доступно авторизованному"""
        data = {
            'product': self.product.uuid,
            'text': 'Текст отзыва',
        }
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        review = Review.objects.get(uuid=response.data['uuid'])
        self.assertEqual(review.user, user)

        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.check_keys_in_dict(response.data, self.instance_detail_keys)
        review = Review.objects.get(uuid=response.data['uuid'])
        self.assertEqual(review.user, user)

    def test_api_create_owner_to_self(self):
        """Тест создания отзыва своему же продукту"""

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        product = Product.objects.create(
            name='prod',
            user=user,
        )
        data = {
            'product': product.uuid,
            'text': 'Текст отзыва',
        }
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_detail(self):
        """Тест доступа к детальной объекта. Доступно всем."""
        api_detail_urn = self.api_detail_urn.format(self.review1.uuid)
        response = self.client.get(api_detail_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.get(api_detail_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.get(api_detail_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_update_not_admin(self):
        """Тест изменения объекта. Доступно админу или владельцу"""
        data = {
            'text': 'Другой текст отзыва',
            'product': self.product.uuid,
        }
        api_update_urn = self.api_update_urn.format(self.review1.uuid)
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser2')
        self.client.force_authenticate(user)
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_update_admin(self):
        """Тест изменения объекта. Доступно админу или владельцу"""
        data = {
            'text': 'Другой текст отзыва',
            'product': self.product.uuid,
        }
        self.review1.refresh_from_db()
        old_text = self.review1.text
        api_update_urn = self.api_update_urn.format(self.review1.uuid)

        # Авторизация
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)

        # Запрос
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.check_keys_in_dict(response.data, self.instance_detail_keys)

        # Проверка нового имени
        self.review1.refresh_from_db()
        new_text = self.review1.text
        self.assertNotEqual(old_text, new_text)
        self.assertEqual(data['text'], new_text)

    def test_api_update_owner(self):
        """Тест изменения объекта. Доступно админу или владельцу"""
        data = {
            'text': 'Другой текст отзыва',
            'product': self.product.uuid,
        }
        user = User.objects.get(username='testuser')
        review = Review.objects.create(
            text='Текст отзыва',
            product=self.product,
            user=user,
        )
        review.refresh_from_db()
        old_text = review.text
        api_update_urn = self.api_update_urn.format(review.uuid)

        # Авторизация
        self.client.force_authenticate(user)

        # Запрос
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.check_keys_in_dict(response.data, self.instance_detail_keys)

        # Проверка нового имени
        review.refresh_from_db()
        new_text = review.text
        self.assertNotEqual(old_text, new_text)
        self.assertEqual(data['text'], new_text)

        # Авторизация за админа
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        # Запрос
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_delete_not_admin(self):
        """Тест удаления объекта. Доступно админу или владельцу"""
        api_delete_urn = self.api_update_urn.format(self.review_to_delete.uuid)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser2')
        self.client.force_authenticate(user)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_delete_admin(self):
        """Тест удаления объекта. Доступно админу или владельцу"""
        # Авторизация
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        api_delete_urn = self.api_update_urn.format(self.review_to_delete.uuid)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Проверка, что объект не удаляется из базы
        self.review_to_delete.refresh_from_db()
        self.assertFalse(self.review_to_delete.is_active)

    def test_api_delete_owner(self):
        """Тест удаления объекта. Доступно админу или владельцу"""
        # Авторизация
        user = User.objects.get(username='testuser')
        review = Review.objects.create(
            text='Текст отзыва',
            product=self.product,
            user=user,
        )
        self.client.force_authenticate(user)
        api_delete_urn = self.api_update_urn.format(review.uuid)
        self.assertTrue(review.is_active)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Проверка, что объект не удаляется из базы
        review.refresh_from_db()
        self.assertFalse(review.is_active)


# class TestReviewsRobust(BaseAPITestCaseMixin, APITestCase):
#     """
#     Класс отзывов на устойчивость.
#     Проверяем работоспособность при большом количестве отзывов на товары
#     """
#
#     @classmethod
#     def setUpTestData(cls):
#         # Пользователи
#         cls.user_admin = cls.create_admin()
#         cls.user1 = User.objects.create(
#             username='testuser',
#         )
#
#         cls.category = Category.objects.create(
#             name='cat'
#         )
#
#         products = Product.objects.bulk_create([
#             Product(name=f'prod{i}', user=cls.user_admin) for i in range(0, 200)
#         ])
#         cls.product = products[0]
#         for product in products:
#             # Добавляем категорию для продукта
#             product.category_set.add(cls.category)
#             # Добавляем 100 отзывов о продукте
#             Review.objects.bulk_create(
#                 [Review(
#                     rating=randint(0, 5),
#                     text='Текст',
#                     product=product,
#                     user=cls.user1,
#                 ) for i in range(30)]
#             )
#
#     def test_api_products_list(self):
#         """Запрос списка продуктоа"""
#
#         t = time.process_time_ns()
#         response = self.client.get(
#             '/api/v1/products/list/?limit=500'
#         )
#         _t = time.process_time_ns()
#         self.assertEqual(response.status_code, status.HTTP_200_OK)

