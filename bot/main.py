import telebot
from mongoengine import connect
from bson import ObjectId
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup)

import flask
from flask import request
import time

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from utils import get_lang
from config import TOKEN, BASE
from words import WORDS
from models.user_model import User
from models.cats_and_products import(
    Category,
    Product,
    Texts,
    Cart,
    OrdersHistory)

WEBHOOK_HOST = '34.90.152.51'
WEBHOOK_PORT = 433 # доступны только 443, 80, 88, 8443
WEBHOOK_LISTEN = '0.0.0.0'
WEBHOOK_SSL_CERT = 'webhook_cert.pem'  # SSL-сертификат
WEBHOOK_SSL_PRIV = 'webhook_pkey.pem'  # Приватный ключ
WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/%s/" % (TOKEN)

bot = telebot.TeleBot(TOKEN)
bot.remove_webhook()
time.sleep(1)
bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH,
               certificate=open(WEBHOOK_SSL_CERT, 'r'))
app = flask.Flask(__name__)
connect(BASE)

bot_messages = list()

@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
   if request.headers.get('content-type') == 'application/json':
       json_string = flask.request.get_data().decode('utf-8')
       update = telebot.types.Update.de_json(json_string)
       bot.process_new_updates([update])
       return ''


@bot.message_handler(commands=['start'])
def send_welcome(message):
    User.get_or_create_user(message)
    lng = get_lang(message)
    message_keyboard = ReplyKeyboardMarkup(one_time_keyboard=True,
                                           resize_keyboard=True,
                                           row_width=2)
    message_keyboard.add(*WORDS[lng]['start_keyboard'].values())
    bot.send_message(message.chat.id, Texts.get_text('Greetings', lng),
                     reply_markup=message_keyboard)


@bot.message_handler(func=lambda message: message.text == WORDS[get_lang(message)]['start_keyboard']['cats'])
def show_cats(message):
    if bot_messages:
        bot.delete_message(message.chat.id, bot_messages[-1])
    lng = get_lang(message)
    cats_kb = InlineKeyboardMarkup(row_width=2)
    cats_buttons = []
    all_cats = Category.objects.all()

    for i in all_cats:
        if i.is_parent:
            cb_data = 'subcategory_' + str(i.id)
            cats_buttons.append(InlineKeyboardButton(text=i.get_title(lng),
                                                     callback_data=cb_data))
    cat_text = WORDS[lng]['cats']

    cats_kb.add(*cats_buttons)
    t = bot.send_message(message.chat.id, text=cat_text,
                         reply_markup=cats_kb, parse_mode='Markdown')
    bot_messages.append(t.message_id)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == 'subcategory')
def sub_cat(call):
    lng = get_lang(call)
    if bot_messages:
        bot.delete_message(call.message.chat.id, bot_messages[-1])
    subcats_kb = InlineKeyboardMarkup(row_width=2)
    subcats_buttons = list()

    category = Category.objects.get(id=call.data.split('_')[1])

    for i in category.sub_categories:
        cb_data = 'category_' + str(i.id)
        if i.is_parent:
            cb_data = 'subcategory_' + str(i.id)
        subcats_buttons.append(InlineKeyboardButton(text=i.get_title(lng), callback_data=cb_data))

    subcats_kb.add(*subcats_buttons)
    t = bot.send_message(call.message.chat.id,
                         text=f'{category.get_title(lng)}:',
                         reply_markup=subcats_kb)
    bot_messages.append(t.message_id)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == 'category')
def products_by_cat(call):
    lng = get_lang(call)
    if bot_messages:
        bot.delete_message(call.message.chat.id, bot_messages[-1])
    cat = Category.objects.filter(id=call.data.split('_')[1]).first()
    products = cat.category_products

    t = bot.send_message(call.message.chat.id, text=f'{cat.get_title(lng)}:')
    bot_messages.append(t.message_id)

    for p in products:
        products_kb = InlineKeyboardMarkup(row_width=2)
        products_kb.add(InlineKeyboardButton(
            text=WORDS[lng]['text_cart'],
            callback_data='addtocart_' + str(p.id)
        ),
            InlineKeyboardButton(
                text=WORDS[lng]['text_detals'],
                callback_data='product_' + str(p.id)
            )
        )
        title = f'_{p.get_title(lng)}_   `$`*{p.price/100}*'
        t = bot.send_photo(call.message.chat.id, p.photos[0],
                           caption=title, reply_markup=products_kb, parse_mode='Markdown')
        bot_messages.append(t.message_id)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == 'addtocart')
def add_to_card(call):
    Cart.create_or_append_to_cart(call)
    # cart = Cart.objects.all().first()


@bot.message_handler(func=lambda message:
                     message.text == WORDS[get_lang(message)]['start_keyboard']['cart'])
def show_cart(message):
    lng = get_lang(message)
    current_user = User.objects.get(user_id=message.from_user.id)
    cart = Cart.objects.filter(user=current_user, is_archived=False).first()

    if not cart:
        bot.send_message(message.chat.id, WORDS[lng]['empty'])
        return

    if not cart.products:
        bot.send_message(message.chat.id, WORDS[lng]['empty'])

    sum_cart = 0
    for prod in cart.products:
        text = f'{prod.title}  `$`*{prod.price / 100}*'
        remove_kb = InlineKeyboardMarkup()
        remove_button = InlineKeyboardButton(text=WORDS[lng]['remove'],
                                             callback_data='rmproduct_' + str(prod.id))
        remove_kb.add(remove_button)
        bot.send_message(message.chat.id, text, reply_markup=remove_kb, parse_mode='Markdown')
        sum_cart += prod.price

    text = f'`{WORDS[lng]["order_sum"]}  ${sum_cart / 100}`\n*{WORDS[lng]["confirm"]}*'

    submit_kb = InlineKeyboardMarkup()
    submit_button = InlineKeyboardButton(
        text=WORDS[lng]['checkout'],
        callback_data='submit'
    )

    submit_kb.add(submit_button)
    bot.send_message(message.chat.id, text, reply_markup=submit_kb, parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == 'rmproduct')
def rm_product_from_cart(call):
    current_user = User.objects.get(user_id=call.from_user.id)
    cart = Cart.objects.filter(user=current_user, is_archived=False).first()
    cart.update(pull__products=ObjectId(call.data.split('_')[1]))
    bot.delete_message(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == 'submit')
def submit_cart(call):
    lng = get_lang(call)
    current_user = User.objects.get(user_id=call.from_user.id)
    cart = Cart.objects.filter(user=current_user, is_archived=False).first()
    cart.is_archived = True

    order_history = OrdersHistory.get_or_create(current_user)
    order_history.orders.append(cart)
    bot.send_message(call.message.chat.id, WORDS[lng]['thanks'])
    cart.save()
    order_history.save()


@bot.callback_query_handler(func=lambda call: call.data.split('_')[0] == 'product')
def product(call):
    lng = get_lang(call)

    medias = list()
    prod = Product.objects.get(id=call.data.split('_')[1])
    # if bot_messages:
    #     c = len(prod.category.category_products)
    #     for i in bot_messages[-c:]:
    #         bot.delete_message(call.message.chat.id, i)
    for p in prod.photos:
        medias.append(telebot.types.InputMediaPhoto(p))

    product_kb = InlineKeyboardMarkup(row_width=2)
    product_kb.add(InlineKeyboardButton(
        text=' \U00002B05 ' + prod.category.get_title(lng),
        callback_data='category_' + str(prod.category.id)
    ),
        InlineKeyboardButton(
            text=WORDS[lng]['text_cart'],
            callback_data='addtocart_' + str(prod.id)
        )
    )

    weight = str(prod.weigth) + WORDS[lng]['g']
    if prod.weigth >= 1000:
        weight = str(prod.weigth/1000) + WORDS[lng]['kg']

    title = f'_{prod.get_title(lng)}_   `$`*{prod.price/100}* \n ' \
            f'`{prod.get_description(lng)} \n' \
            f'{WORDS[lng]["weight"]} {weight}\n' \
            f'{WORDS[lng]["quantity"]} {prod.quantity}`'
    try:
        bot.send_media_group(call.message.chat.id, medias)
    except:
        bot.send_photo(call.message.chat.id,
                       prod.photos[0])

    t = bot.send_message(call.message.chat.id, title,
                         reply_markup=product_kb, parse_mode='Markdown')
    bot_messages.append(t.message_id)


@bot.message_handler(func=lambda message: message.text == WORDS[get_lang(message)]['start_keyboard']['hist'])
def show_history(message):
    lng = get_lang(message)
    current_user = User.objects.get(user_id=message.from_user.id)
    carts = Cart.objects.filter(user=current_user, is_archived=True)
    text = ''

    if not carts:
        bot.send_message(message.chat.id, WORDS[lng]['history_empty'])
        return

    for cart in carts:
        text += '\n\n'
        sum_price = 0
        if not cart.products:
            continue
        for prod in cart.products:
            text += f'{prod.title}  $*{prod.price / 100}* \n'
            sum_price += prod.price
        text += f'`{WORDS[lng]["order_sum"]}  ${sum_price / 100}` \n'
    bot.send_message(message.chat.id, text=text, parse_mode='Markdown')


@bot.message_handler()
def rep_keyboard(message):
    lng = get_lang(message)
    if WORDS[lng]['start_keyboard']['news'] in message.text:
        bot.send_message(message.chat.id, Texts.get_text('news', lng))
    if WORDS[lng]['start_keyboard']['info'] in message.text:
        bot.send_message(message.chat.id, Texts.get_text('info', lng))


if __name__ == "__main__":
    # bot.polling()
    app.run(host=WEBHOOK_LISTEN,
            port=WEBHOOK_PORT,
            ssl_context=(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV),
            debug=True)


