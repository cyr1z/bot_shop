from mongoengine import *
from models.user_model import User

class Category(Document):
    title = StringField(max_length=100)
    title_ru = StringField(max_length=100)
    description = StringField(max_length=3200)
    description_ru = StringField(max_length=3200)
    sub_categories = ListField(ReferenceField('self'))

    @property
    def is_parent(self):
        if len(self.sub_categories):
            return True

    @property
    def category_products(self):
        return Product.objects.filter(category=self, is_avilable=True)


    def get_description(self, lang='en'):
        if lang == 'ru':
            return self.description_ru
        return self.description


    def get_title(self, lang='en'):
        if lang == 'ru':
            return self.title_ru
        return self.title

    def __str__(self):
        return f'{self.title}'


class Product(Document):
    title = StringField(max_length=300)
    description = StringField(max_length=4096)
    title_ru = StringField(max_length=300)
    description_ru = StringField(max_length=4096)
    price = IntField(min_value=0)
    is_discount = BooleanField(default=False)
    quantity = IntField(min_value=0)
    category = ReferenceField(Category)
    weigth = FloatField(min_value=0, null=True)
    is_avilable = BooleanField(default=True)
    photos = ListField()

    def get_description(self, lang='en'):
        if lang == 'ru':
            return self.description_ru
        return self.description

    def get_title(self, lang='en'):
        if lang == 'ru':
            return self.title_ru
        return self.title

    def __str__(self):
        return f'{self.title} category - {self.category}'


class Texts(Document):
    title = StringField()
    text = StringField(max_length=4096)
    text_ru = StringField(max_length=4096)

    @classmethod
    def get_text(cls, title, lang='en'):
        if lang == 'ru':
            return cls.objects.filter(title=title).first().text_ru
        return cls.objects.filter(title=title).first().text


class Cart(Document):
    user = ReferenceField(User, required=True)
    products = ListField(ReferenceField(Product))
    is_archived = BooleanField(default=False)

    @property
    def get_sum(self):
        cart_sum = 0
        for p in self.products:
            cart_sum += p.price

        return cart_sum/100

    @classmethod
    def create_or_append_to_cart(cls, call):
        product_id = call.data.split('_')[1]
        user_id = call.from_user.id
        user = User.objects.get(user_id=user_id)
        user_cart = cls.objects.filter(user=user, is_archived=False).first()
        product = Product.objects.get(id=product_id)

        if user_cart and not user_cart.is_archived:
            user_cart.products.append(product)
            user_cart.save()
        else:
            cls(user=user, products=[product]).save()

    def clean_cart(self):
        self.products = []
        self.save()

    def __str__(self):
        return str(self.products)


class OrdersHistory(Document):
    user = ReferenceField(User)
    orders = ListField(ReferenceField(Cart))

    @classmethod
    def get_or_create(cls, user):
        history = cls.objects.filter(user=user).first()
        if history:
            return history
        else:
            return cls(user)
