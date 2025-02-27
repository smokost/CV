from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from marketapp.models import (
    Category,
    Product,
)
from restapiapp.productsapi.serializers import (
    ProductSerializer,
)
from restapiapp.categoriesapi.serializers import (
    CategorySerializer,
)
from utils.tests import (
    BaseModelAPITestCaseMixin,
)

User = get_user_model()


class TestProductsAPI(BaseModelAPITestCaseMixin, APITestCase):
    """
    Класс для тестирования API продуктов
    """

    serializer_class = ProductSerializer
    model_class = Product
    instance_detail_keys = [
        'uuid',
        'is_active',
        'name',
        'desc',
        'logo',
        'logo_small',
        'logo_big',
        'logo_large',
        'time_created',
        'time_updated',
        'user',
        'price',
        'rating',
        # 'feature_set',
    ]
    api_list_urn = '/api/v1/products/'
    api_create_urn = api_list_urn
    api_detail_urn = '/api/v1/products/{}/'
    api_update_urn = api_detail_urn
    api_delete_urn = api_detail_urn
    api_bulk_delete_urn = api_list_urn

    bulk_delete_query = {'category': '^category_bulk_delete_parent$'}

    @classmethod
    def setUpTestData(cls):
        cls.user_admin = cls.create_admin()

        Category.objects.bulk_create([
            Category(name=f'cat{i}') for i in range(0, 10)
        ])

        Category.objects.bulk_create([
            Category(name=f'cat{i}', is_active=False) for i in range(10, 20)
        ])

        cls.category_parent1 = Category.objects.filter(is_active=True).first()
        products = Product.objects.bulk_create([
            Product(name=f'prod{i}', user=cls.user_admin) for i in range(0, 10)
        ])
        cls.product = products[0]
        for product in products:
            product.category_set.add(cls.category_parent1)

        cls.category_parent2 = Category.objects.filter(is_active=True).last()
        products += Product.objects.bulk_create([
            Product(name=f'prod{i}', is_active=False, user=cls.user_admin) for i in range(10, 20)
        ])
        for product in products:
            product.category_set.add(cls.category_parent2)

        cls.product_to_delete = Product.objects.create(
            name='product_to_delete',
            user=cls.user_admin,
        )

        cls.category_bulk_delete_parent = Category.objects.create(name='category_bulk_delete_parent')
        products = Product.objects.bulk_create([
            Product(name=f'delete_me{i}', user=cls.user_admin) for i in range(0, 5)
        ])
        for product in products:
            product.category_set.add(cls.category_bulk_delete_parent)

        User.objects.create(
            username='testuser',
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
        query_filter = {'productcategorym2m__category__uuid': self.category_parent1.uuid}
        self.get_api_list_test(None, query, query_filter)

    def test_api_get_list_search_by_category_name(self):
        """Тест запроса списка объектов. Поиск по имени категории"""
        query = {'category': self.category_parent1.name}
        query_filter = {'productcategorym2m__category__name': self.category_parent1.name}
        self.get_api_list_test(None, query, query_filter)

    def test_api_create_not_admin(self):
        """Тест создания нового объекта. Доступно авторизованному"""
        data = {
            'name': 'ИмяПродукта'
        }
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product = Product.objects.get(uuid=response.data['uuid'])
        self.assertEqual(product.user, user)

        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.post(self.api_create_urn, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.check_keys_in_dict(response.data, self.instance_detail_keys)
        product = Product.objects.get(uuid=response.data['uuid'])
        self.assertEqual(product.user, user)

    # def test_create_product_admin(self):
    #     """Тест создания нового продукта. Доступно только админу"""
    #     data = {
    #         'name': 'ИмяПродукта'
    #     }
    #     user = User.objects.get(username='admin')
    #     self.client.force_authenticate(user)
    #     response = self.client.post(self.api_create_urn, data)
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #     self.check_keys_in_dict(response.data, self.instance_detail_keys)

    def test_api_detail(self):
        """Тест доступа к детальной объекта. Доступно всем."""
        api_detail_urn = self.api_detail_urn.format(self.product.uuid)
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
            'name': 'ДругоеИмяПродукта'
        }
        api_update_urn = self.api_update_urn.format(self.product.uuid)
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_update_admin(self):
        """Тест изменения объекта. Доступно админу или владельцу"""
        data = {
            'name': 'ДругоеИмяПродукта'
        }
        self.product.refresh_from_db()
        old_name = self.product.name
        api_update_urn = self.api_update_urn.format(self.product.uuid)

        # Авторизация
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)

        # Запрос
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.check_keys_in_dict(response.data, self.instance_detail_keys)

        # Проверка нового имени
        self.product.refresh_from_db()
        new_name = self.product.name
        self.assertNotEqual(old_name, new_name)
        self.assertEqual(data['name'], new_name)

    def test_api_update_owner(self):
        """Тест изменения объекта. Доступно админу или владельцу"""
        data = {
            'name': 'ДругоеИмяПродукта'
        }
        user = User.objects.get(username='testuser')
        product = Product.objects.create(
            name='ИмяПродукта',
            user=user,
        )
        product.refresh_from_db()
        old_name = product.name
        api_update_urn = self.api_update_urn.format(product.uuid)

        # Авторизация
        self.client.force_authenticate(user)

        # Запрос
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.check_keys_in_dict(response.data, self.instance_detail_keys)

        # Проверка нового имени
        product.refresh_from_db()
        new_name = product.name
        self.assertNotEqual(old_name, new_name)
        self.assertEqual(data['name'], new_name)

        # Авторизация за админа
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        # Запрос
        response = self.client.put(api_update_urn, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_delete_not_admin(self):
        """Тест удаления объекта. Доступно админу или владельцу"""
        api_delete_urn = self.api_update_urn.format(self.product_to_delete.uuid)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_api_delete_admin(self):
        """Тест удаления объекта. Доступно админу или владельцу"""
        # Авторизация
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        api_delete_urn = self.api_update_urn.format(self.product_to_delete.uuid)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Проверка, что объект не удаляется из базы
        self.product_to_delete.refresh_from_db()
        self.assertFalse(self.product_to_delete.is_active)

    def test_api_delete_owner(self):
        """Тест удаления объекта. Доступно админу или владельцу"""
        # Авторизация
        user = User.objects.get(username='testuser')
        product = Product.objects.create(
            name='ИмяПродукта',
            user=user,
        )
        self.client.force_authenticate(user)
        api_delete_urn = self.api_update_urn.format(product.uuid)
        self.assertTrue(product.is_active)
        response = self.client.delete(api_delete_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Проверка, что объект не удаляется из базы
        product.refresh_from_db()
        self.assertFalse(product.is_active)

    # def test_bulk_delete_products_not_admin(self):
    #     """Тест массового удаления продуктов. Доступно только админу"""
    #     response = self.client.delete(self.api_bulk_delete_urn)
    #     self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    #
    #     user = User.objects.get(username='testuser')
    #     self.client.force_authenticate(user)
    #     response = self.client.delete(self.api_bulk_delete_urn)
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # def test_bulk_delete_products_admin(self):
    #     """Тест массового удаления продуктов. Доступно только админу"""
    #     # Авторизация
    #     user = User.objects.get(username='admin')
    #     self.client.force_authenticate(user)
    #     products_count = Product.objects.filter(
    #         productcategorym2m__category=self.category_bulk_delete_parent
    #     ).count()
    #     productcategorym2m_count = ProductCategoryM2M.objects.filter(
    #         category=self.category_bulk_delete_parent
    #     ).count()
    #     response = self.client.delete(
    #         self.api_bulk_delete_urn,
    #         QUERY_STRING=urlencode(self.bulk_delete_query, doseq=True)
    #     )
    #     self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    #     self.assertEqual(response.data['deleted'][0], productcategorym2m_count + products_count)
    #     self.assertEqual(response.data['deleted'][1]['marketapp.ProductCategoryM2M'], productcategorym2m_count)
    #     self.assertEqual(response.data['deleted'][1]['marketapp.Product'], products_count)


class TestCategoryProductsAPI(APITestCase):
    """
    Класс для тестирования списка продуктов категории.
    Или списка категорий продукта.
    """

    api_products_list_urn = '/api/v1/products/?category={}'
    api_categories_list_urn = '/api/v1/categories/?product={}'
    api_product_categories_urn = '/api/v1/products/{}/categories/'
    api_product_category_urn = '/api/v1/products/{}/categories/{}/'

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='admin', is_staff=True,)
        user = User.objects.create(username='testuser')
        User.objects.create(username='testuser2')

        cls.category1 = Category(name='cat1')
        cls.category2 = Category(name='cat2')
        cls.category3 = Category(name='cat3')
        Category.objects.bulk_create([cls.category1, cls.category2, cls.category3])

        products = Product.objects.bulk_create([
            Product(name=f'prod{i}', user=user) for i in range(29)
        ])
        cls.product = products[0]
        for i, product in enumerate(products):
            cat = cls.category1 if i % 2 else cls.category2
            product.category_set.add(cat)
            product.category_set.add(cls.category3)

    def test_category_products_list(self):
        """Тест списка продуктов категории"""
        api_list_urn = self.api_products_list_urn.format(self.category1.uuid)
        response = self.client.get(api_list_urn)
        queryset = Product.objects.filter(productcategorym2m__category=self.category1)
        serializer = ProductSerializer(queryset, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], queryset.count())
        self.assertEqual(response.data['count'], 14)
        self.assertEqual(response.data['results'], serializer.data)

    def test_product_categories_list(self):
        """Тест списка продуктов категории"""
        api_list_urn = self.api_categories_list_urn.format(self.product.uuid)
        response = self.client.get(api_list_urn)
        queryset = Category.objects.filter(productcategorym2m__product=self.product)
        serializer = CategorySerializer(queryset, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], queryset.count())
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['results'], serializer.data)

    def test_product_category_list(self):
        """Запрос списка категорий продукта. Доступно всем."""
        api_product_categories_urn = self.api_product_categories_urn.format(self.product.uuid)
        response = self.client.get(api_product_categories_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.get(api_product_categories_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.get(api_product_categories_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_product_category_create(self):
        """Создание связи категория-продукт. Доступно админу или создателю товара."""
        data = {'category': self.category1.uuid}

        product = Product.objects.create(
            name='prod_without',
            user=User.objects.get(username='testuser'),
        )
        api_product_categories_urn = self.api_product_categories_urn.format(
            product.uuid
        )

        # Запрос от неавторизованного
        response = self.client.post(
            api_product_categories_urn,
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Запрос от не владельца
        user = User.objects.get(username='testuser2')
        self.client.force_authenticate(user)
        response = self.client.post(
            api_product_categories_urn,
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Запрос от владельца
        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.post(
            api_product_categories_urn,
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Повторный запрос от владельца
        response = self.client.post(
            api_product_categories_urn,
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Запрос от админа
        data = {'category': self.category2.uuid}
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.post(
            api_product_categories_urn,
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_product_category_bulk_delete(self):
        """Удаление всех связей категория-продукт. Доступно админу или создателю товара."""

        product: Product = Product.objects.create(
            name='prod_without',
            user=User.objects.get(username='testuser'),
        )
        product.category_set.add(self.category1)
        product.category_set.add(self.category2)
        api_product_categories_urn = self.api_product_categories_urn.format(
            product.uuid
        )

        # Запрос от неавторизованного
        response = self.client.delete(api_product_categories_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Запрос от не владельца
        user = User.objects.get(username='testuser2')
        self.client.force_authenticate(user)
        response = self.client.delete(api_product_categories_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Запрос от владельца
        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.delete(api_product_categories_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Повторный запрос от владельца
        response = self.client.delete(api_product_categories_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Запрос от админа
        product: Product = Product.objects.create(
            name='prod_without',
            user=User.objects.get(username='testuser'),
        )
        product.category_set.add(self.category1)
        product.category_set.add(self.category2)
        api_product_categories_urn = self.api_product_categories_urn.format(
            product.uuid
        )
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.delete(api_product_categories_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_product_category_delete(self):
        """Удаление связи категория-продукт. Доступно админу или создателю товара."""

        product = Product.objects.create(
            name='prod_without',
            user=User.objects.get(username='testuser'),
        )
        product.category_set.add(self.category1)
        product.category_set.add(self.category2)
        api_product_category_urn = self.api_product_category_urn.format(
            product.uuid,
            self.category1.uuid,
        )

        # Запрос от неавторизованного
        response = self.client.delete(api_product_category_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Запрос от не владельца
        user = User.objects.get(username='testuser2')
        self.client.force_authenticate(user)
        response = self.client.delete(api_product_category_urn)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Запрос от владельца
        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.delete(api_product_category_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Повторный запрос от владельца
        response = self.client.delete(api_product_category_urn)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Запрос от админа
        api_product_category_urn = self.api_product_category_urn.format(
            product.uuid,
            self.category2.uuid,
        )
        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.delete(api_product_category_urn)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_product_category_detail(self):
        """Запрос детальной категории продукта. Доступно всем."""
        api_product_category_urn = self.api_product_category_urn.format(
            self.product.uuid,
            self.category3.uuid,
        )
        response = self.client.get(api_product_category_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(username='testuser')
        self.client.force_authenticate(user)
        response = self.client.get(api_product_category_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(username='admin')
        self.client.force_authenticate(user)
        response = self.client.get(api_product_category_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
