from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.http import urlencode
from rest_framework import status
from rest_framework.test import APITestCase

from marketapp.models import Category
from restapiapp.categoriesapi.serializers import (
    CategorySerializer,
)
from utils.tests import (
    BaseModelAPITestCaseMixin,
)

User = get_user_model()


class TestCategoriesAPI(BaseModelAPITestCaseMixin, APITestCase):
    """
    Класс для тестирования API категорий
    """

    serializer_class = CategorySerializer
    model_class = Category
    instance_detail_keys = [
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
    ]
    api_list_urn = '/api/v1/categories/'
    api_create_urn = api_list_urn
    api_detail_urn = '/api/v1/categories/{}/'
    api_update_urn = api_detail_urn
    api_delete_urn = api_detail_urn
    api_bulk_delete_urn = api_list_urn
    bulk_delete_query = {'parent': '^category_bulk_delete_parent$'}

    @classmethod
    def setUpTestData(cls):
        cls.create_admin()

        Category.objects.bulk_create([
            Category(name=f'cat{i}') for i in range(0, 10)
        ])

        Category.objects.bulk_create([
            Category(name=f'cat{i}', is_active=False) for i in range(10, 20)
        ])

        cls.category_parent = Category.objects.filter(is_active=True).first()
        Category.objects.bulk_create([
            Category(name=f'cat{i}', parent=cls.category_parent) for i in range(0, 5)
        ])

        cls.category_to_delete = Category.objects.create(name='category_to_delete')

        cls.category_bulk_delete_parent = Category.objects.create(name='category_bulk_delete_parent')
        Category.objects.bulk_create([
            Category(name=f'delete_me{i}', parent=cls.category_bulk_delete_parent) for i in range(0, 5)
        ])

        User.objects.create(
            username='testuser',
        )

    def test_get_category_list_admin(self):
        """Тест запроса списка категорий админом"""
        self.get_api_list_test('admin')
        self.get_api_list_test('admin', {'is_active': True})
        self.get_api_list_test('admin', {'is_active': False})

    def test_get_category_list_not_admin(self):
        """Тест запроса списка категорий не админом"""
        self.get_api_list_test('testuser')
        self.get_api_list_test('testuser', {'is_active': True})
        self.get_api_list_test('testuser', {'is_active': False})

    def test_get_category_list_anonymous(self):
        """Тест запроса списка категорий не админом"""
        self.get_api_list_test(None)
        self.get_api_list_test(None, {'is_active': True})
        self.get_api_list_test(None, {'is_active': False})

    def test_get_category_list_search_by_parent_uuid(self):
        """Тест запроса списка категорий. Поиск по uuid родительской категории"""
        query = {'parent': self.category_parent.uuid}
        query_filter = {'parent__uuid': self.category_parent.uuid}
        self.get_api_list_test(None, query, query_filter)

    def test_get_category_list_search_by_parent_name(self):
        """Тест запроса списка категорий. Поиск по имени родительской категории"""
        query = {'parent': self.category_parent.name}
        query_filter = {'parent__name': self.category_parent.name}
        self.get_api_list_test(None, query, query_filter)

    def test_create_category_not_admin(self):
        """Тест создания новой категории. Доступно только админу"""
        data = {
            'name': 'ИмяКатегории'
        }
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_category_admin(self):
        """Тест создания новой категории. Доступно только админу"""
        data = {
            'name': 'ИмяКатегории'
        }
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.check_keys_in_dict(response.data, self.instance_detail_keys)

    def test_detail_category(self):
        """Тест доступа к детальной категории. Доступно всем."""
        api_detail_urn = self.api_detail_urn.format(self.category_parent.uuid)
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

    def test_update_category_not_admin(self):
        """Тест изменения категории. Доступно только админу"""
        data = {
            'name': 'ДругоеИмяКатегории'
        }
        api_update_urn = self.api_update_urn.format(self.category_parent.uuid)
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_category_admin(self):
        """Тест изменения категории. Доступно только админу"""
        data = {
            'name': 'ДругоеИмяКатегории'
        }
        self.category_parent.refresh_from_db()
        old_name = self.category_parent.name
        api_update_urn = self.api_update_urn.format(self.category_parent.uuid)

        # Авторизация
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)

        # Запрос
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.check_keys_in_dict(response.data, self.instance_detail_keys)

        # Проверка нового имени
        self.category_parent.refresh_from_db()
        new_name = self.category_parent.name
        self.assertNotEqual(old_name, new_name)
        self.assertEqual(data['name'], new_name)

    def test_delete_category_not_admin(self):
        """Тест удаления категории. Доступно только админу"""
        api_delete_urn = self.api_update_urn.format(self.category_to_delete.uuid)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_category_admin(self):
        """Тест удаления категории. Доступно только админу"""
        # Авторизация
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        api_delete_urn = self.api_update_urn.format(self.category_to_delete.uuid)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_bulk_delete_categories_not_admin(self):
        """Тест массового удаления категории. Доступно только админу"""
        response = self.client.delete(self.api_bulk_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.delete(self.api_bulk_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_bulk_delete_categories_admin(self):
        """Тест массового удаления категории. Доступно только админу"""
        # Авторизация
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        categories_count = Category.objects.filter(parent=self.category_bulk_delete_parent).count()
        response = self.client.delete(
            self.api_bulk_delete_urn,
            QUERY_STRING=urlencode(self.bulk_delete_query, doseq=True)
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        if settings.DEBUG:
            self.assertEqual(response.data['deleted'][0], categories_count)
            self.assertEqual(response.data['deleted'][1]['marketapp.Category'], categories_count)
