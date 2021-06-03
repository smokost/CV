from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from marketapp.models import (
    Category,
    Product,
    Feature,
    FeatureValue,
)
from utils.tests import (
    BaseAPITestCaseMixin,
)

User = get_user_model()


class TestCategoriesAPI(BaseAPITestCaseMixin, APITestCase):
    """
    Класс для тестирования API списка свойств категории или продукта
    """

    category_features_urn = '/api/v1/categories/{}/features/'
    product_features_urn = '/api/v1/products/{}/features/'

    @classmethod
    def setUpTestData(cls):
        cls.user_admin = cls.create_admin()
        cls.user1 = User.objects.create(username='testuser')

        # Создаем разные категории
        categories = Category.objects.bulk_create([
            Category(name=f'cat{i}') for i in range(0, 3)
        ])
        cls.category1: Category = categories[0]
        cls.category2: Category = categories[1]

        # Создаем свойства
        features = Feature.objects.bulk_create(
            [Feature(name=f'feature{i}') for i in range(0, 3)]
        )
        cls.feature1: Feature = features[0]
        cls.feature2: Feature = features[1]

        # Создаем значения свойств
        featurevalues = FeatureValue.objects.bulk_create(
            [FeatureValue(name=f'val1{i}', feature=cls.feature1) for i in range(0, 3)]
        )
        cls.featurevalue1: FeatureValue = featurevalues[0]
        featurevalues = FeatureValue.objects.bulk_create(
            [FeatureValue(name=f'val2{i}', feature=cls.feature2) for i in range(0, 3)]
        )
        cls.featurevalue2: FeatureValue = featurevalues[0]

        # Создаем разные продукты и присоединяем их к категориям
        products = Product.objects.bulk_create([
            Product(name=f'prod1{i}', user=cls.user1) for i in range(0, 3)
        ])
        cls.product1: Product = products[0]
        for product in products:
            product.category_set.add(cls.category1)
            product.feature_set.add(cls.featurevalue1)

        # Еще продукты
        products += Product.objects.bulk_create([
            Product(name=f'prod2{i}', user=cls.user1) for i in range(0, 3)
        ])
        cls.product2: Product = products[0]
        for product in products:
            product.category_set.add(cls.category1)
            product.category_set.add(cls.category2)
            product.feature_set.add(cls.featurevalue1)
            product.feature_set.add(cls.featurevalue2)

    def test_get_list_products_features(self):
        """
        Тест получения списка свойств для продукта.
        """

        self.client.logout()
        for product in (self.product1, self.product2, ):
            product_features_urn = self.product_features_urn.format(product.uuid)
            response = self.client.get(product_features_urn)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Проверяем просто по количеству элементов
            self.assertEqual(response.data['count'], product.feature_set.count())
            queryset = product.feature_set.all()[0].feature.featurevalue_set.filter(
                productfeaturem2m__product__uuid=product.uuid
            )
            self.assertEqual(
                len(response.data['results'][0]['featurevalue_set']),
                queryset.count(),
            )

    def test_get_list_categories_features(self):
        """
        Тест получения списка свойств для категории.
        Пересечение свойств всех продуктов.
        """

        self.client.logout()
        category_features_urn = self.category_features_urn.format(self.category1.uuid)
        response = self.client.get(category_features_urn)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data['count'], 0)

        # Проверяем просто по количеству элементов
        queryset = Feature.objects.filter(
            featurevalue__productfeaturem2m__product__productcategorym2m__category__uuid=self.category1.uuid
        ).distinct()
        self.assertEqual(response.data['count'], queryset.count())
        for i, obj in enumerate(queryset):
            queryset_ = FeatureValue.objects.filter(
                feature=obj,
                productfeaturem2m__product__productcategorym2m__category__uuid=self.category1.uuid
            ).distinct()
            self.assertEqual(
                len(response.data['results'][i]['featurevalue_set']),
                queryset_.count()
            )

