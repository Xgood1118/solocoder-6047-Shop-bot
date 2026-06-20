from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData
from loader import db

product_cb = CallbackData('product', 'id', 'action')


def product_markup(idx='', price=0, quantity_in_cart=0):

    global product_cb

    markup = InlineKeyboardMarkup()

    if quantity_in_cart > 0:
        markup.add(InlineKeyboardButton(f'✅ В корзине: {quantity_in_cart} шт. | + {price}₽', callback_data=product_cb.new(id=idx, action='add')))
    else:
        markup.add(InlineKeyboardButton(f'Добавить в корзину - {price}₽', callback_data=product_cb.new(id=idx, action='add')))

    return markup