import logging
import json
import time
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.inline.products_from_cart import product_markup, product_cb
from aiogram.utils.callback_data import CallbackData
from keyboards.default.markups import *
from aiogram.types.chat import ChatActions
from states import CheckoutState
from loader import dp, db, bot
from filters import IsUser
from .menu import cart


DELIVERY_SLOTS = {
    'morning': {'name_ru': 'Утро', 'time_range': '09:00 - 13:00'},
    'afternoon': {'name_ru': 'День', 'time_range': '13:00 - 18:00'},
    'evening': {'name_ru': 'Вечер', 'time_range': '18:00 - 22:00'}
}

delivery_slot_cb = CallbackData('delivery_slot', 'slot_id')


@dp.message_handler(IsUser(), text=cart)
async def process_cart(message: Message, state: FSMContext):

    cart_data = db.fetchall(
        'SELECT * FROM cart WHERE cid=?', (message.chat.id,))

    if len(cart_data) == 0:

        await message.answer('Ваша корзина пуста.')

    else:

        await bot.send_chat_action(message.chat.id, ChatActions.TYPING)
        async with state.proxy() as data:
            data['products'] = {}

        order_cost = 0

        for _, idx, count_in_cart in cart_data:

            product = db.fetchone('SELECT * FROM products WHERE idx=?', (idx,))

            if product == None:

                db.query('DELETE FROM cart WHERE idx=?', (idx,))

            else:
                _, title, body, image, price, _ = product
                order_cost += price

                async with state.proxy() as data:
                    data['products'][idx] = [title, price, count_in_cart]

                markup = product_markup(idx, count_in_cart)
                text = f'<b>{title}</b>\n\n{body}\n\nЦена: {price}₽.'

                await message.answer_photo(photo=image,
                                           caption=text,
                                           reply_markup=markup)

        if order_cost != 0:
            markup = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
            markup.add('📦 Оформить заказ')

            await message.answer('Перейти к оформлению?',
                                 reply_markup=markup)


@dp.callback_query_handler(IsUser(), product_cb.filter(action='count'))
@dp.callback_query_handler(IsUser(), product_cb.filter(action='increase'))
@dp.callback_query_handler(IsUser(), product_cb.filter(action='decrease'))
async def product_callback_handler(query: CallbackQuery, callback_data: dict, state: FSMContext):

    idx = callback_data['id']
    action = callback_data['action']

    if 'count' == action:

        async with state.proxy() as data:

            if 'products' not in data.keys():

                await process_cart(query.message, state)

            else:

                await query.answer('Количество - ' + data['products'][idx][2])

    else:

        async with state.proxy() as data:

            if 'products' not in data.keys():

                await process_cart(query.message, state)

            else:

                data['products'][idx][2] += 1 if 'increase' == action else -1
                count_in_cart = data['products'][idx][2]

                if count_in_cart == 0:

                    db.query('''DELETE FROM cart
                    WHERE cid = ? AND idx = ?''', (query.message.chat.id, idx))

                    await query.message.delete()
                else:

                    db.query('''UPDATE cart 
                    SET quantity = ? 
                    WHERE cid = ? AND idx = ?''', (count_in_cart, query.message.chat.id, idx))

                    await query.message.edit_reply_markup(product_markup(idx, count_in_cart))


@dp.message_handler(IsUser(), text='📦 Оформить заказ')
async def process_checkout(message: Message, state: FSMContext):

    await CheckoutState.check_cart.set()
    await checkout(message, state)


async def checkout(message, state):
    answer = ''
    total_price = 0

    async with state.proxy() as data:

        for title, price, count_in_cart in data['products'].values():

            tp = count_in_cart * price
            answer += f'<b>{title}</b> * {count_in_cart}шт. = {tp}₽\n'
            total_price += tp

    await message.answer(f'{answer}\nОбщая сумма заказа: {total_price}₽.',
                         reply_markup=check_markup())


@dp.message_handler(IsUser(), lambda message: message.text not in [all_right_message, back_message], state=CheckoutState.check_cart)
async def process_check_cart_invalid(message: Message):
    await message.reply('Такого варианта не было.')


@dp.message_handler(IsUser(), text=back_message, state=CheckoutState.check_cart)
async def process_check_cart_back(message: Message, state: FSMContext):
    await state.finish()
    await process_cart(message, state)


@dp.message_handler(IsUser(), text=all_right_message, state=CheckoutState.check_cart)
async def process_check_cart_all_right(message: Message, state: FSMContext):
    await CheckoutState.next()
    await message.answer('Укажите свое имя.',
                         reply_markup=back_markup())


@dp.message_handler(IsUser(), text=back_message, state=CheckoutState.name)
async def process_name_back(message: Message, state: FSMContext):
    await CheckoutState.check_cart.set()
    await checkout(message, state)


@dp.message_handler(IsUser(), state=CheckoutState.name)
async def process_name(message: Message, state: FSMContext):

    async with state.proxy() as data:

        data['name'] = message.text

        if 'address' in data.keys():

            await CheckoutState.delivery_slot.set()
            await show_delivery_slots(message)

        else:

            await CheckoutState.next()
            await message.answer('Укажите свой адрес места жительства.',
                                 reply_markup=back_markup())


@dp.message_handler(IsUser(), text=back_message, state=CheckoutState.address)
async def process_address_back(message: Message, state: FSMContext):

    async with state.proxy() as data:

        await message.answer('Изменить имя с <b>' + data['name'] + '</b>?',
                             reply_markup=back_markup())

    await CheckoutState.name.set()


@dp.message_handler(IsUser(), state=CheckoutState.address)
async def process_address(message: Message, state: FSMContext):

    async with state.proxy() as data:
        data['address'] = message.text

    await CheckoutState.delivery_slot.set()
    await show_delivery_slots(message)


@dp.message_handler(IsUser(), text=back_message, state=CheckoutState.delivery_slot)
async def process_delivery_slot_back(message: Message, state: FSMContext):

    await CheckoutState.address.set()

    async with state.proxy() as data:
        await message.answer('Изменить адрес с <b>' + data['address'] + '</b>?',
                             reply_markup=back_markup())


@dp.callback_query_handler(IsUser(), delivery_slot_cb.filter(), state=CheckoutState.delivery_slot)
async def process_delivery_slot_select(query: CallbackQuery, callback_data: dict, state: FSMContext):
    slot_id = callback_data['slot_id']

    if slot_id not in DELIVERY_SLOTS:
        await query.answer('Неверный вариант.')
        return

    slot = DELIVERY_SLOTS[slot_id]
    slot_data = {
        'slot_id': slot_id,
        'name_ru': slot['name_ru'],
        'time_range': slot['time_range'],
        'timestamp': int(time.time())
    }

    async with state.proxy() as data:
        data['delivery_slot'] = slot_data

    await query.answer(f'Выбран слот: {slot["name_ru"]}')
    await confirm(message=query.message, state=state)
    await CheckoutState.confirm.set()


async def show_delivery_slots(message):
    markup = InlineKeyboardMarkup(row_width=1)

    for slot_id, slot_data in DELIVERY_SLOTS.items():
        button_text = f'{slot_data["name_ru"]} ({slot_data["time_range"]})'
        markup.add(InlineKeyboardButton(
            button_text,
            callback_data=delivery_slot_cb.new(slot_id=slot_id)
        ))

    markup.add(InlineKeyboardButton(back_message, callback_data='delivery_slot_back'))

    await message.answer('Выберите удобное время доставки:', reply_markup=markup)


@dp.callback_query_handler(IsUser(), lambda c: c.data == 'delivery_slot_back', state=CheckoutState.delivery_slot)
async def process_delivery_slot_back_cb(query: CallbackQuery, state: FSMContext):
    await CheckoutState.address.set()

    async with state.proxy() as data:
        await query.message.answer('Изменить адрес с <b>' + data['address'] + '</b>?',
                                   reply_markup=back_markup())


async def confirm(message, state):

    async with state.proxy() as data:
        delivery_slot = data.get('delivery_slot', {})

    slot_text = ''
    if delivery_slot:
        slot_text = f'\n\n🕐 Время доставки: <b>{delivery_slot.get("name_ru", "")}</b> ({delivery_slot.get("time_range", "")})'

    await message.answer(f'Убедитесь, что все правильно оформлено и подтвердите заказ.{slot_text}',
                         reply_markup=confirm_markup())


@dp.message_handler(IsUser(), lambda message: message.text not in [confirm_message, back_message], state=CheckoutState.confirm)
async def process_confirm_invalid(message: Message):
    await message.reply('Такого варианта не было.')


@dp.message_handler(IsUser(), text=back_message, state=CheckoutState.confirm)
async def process_confirm_back(message: Message, state: FSMContext):

    await CheckoutState.delivery_slot.set()
    await show_delivery_slots(message)


@dp.message_handler(IsUser(), text=confirm_message, state=CheckoutState.confirm)
async def process_confirm(message: Message, state: FSMContext):

    enough_money = True  # enough money on the balance sheet
    markup = ReplyKeyboardRemove()

    if enough_money:

        logging.info('Deal was made.')

        async with state.proxy() as data:

            cid = message.chat.id
            products = [idx + '=' + str(quantity)
                        for idx, quantity in db.fetchall('''SELECT idx, quantity FROM cart
            WHERE cid=?''', (cid,))]  # idx=quantity

            delivery_slot_json = ''
            delivery_slot_text = ''
            if 'delivery_slot' in data:
                delivery_slot_json = json.dumps(data['delivery_slot'], ensure_ascii=False)
                delivery_slot_text = f'\n🕐 Время доставки: <b>{data["delivery_slot"]["name_ru"]}</b> ({data["delivery_slot"]["time_range"]})'

            db.query('INSERT INTO orders (cid, usr_name, usr_address, products, delivery_slot) VALUES (?, ?, ?, ?, ?)',
                     (cid, data['name'], data['address'], ' '.join(products), delivery_slot_json))

            db.query('DELETE FROM cart WHERE cid=?', (cid,))

            await message.answer('Ок! Ваш заказ уже в пути 🚀\nИмя: <b>' + data['name'] + '</b>\nАдрес: <b>' + data['address'] + '</b>' + delivery_slot_text,
                                 reply_markup=markup)
    else:

        await message.answer('У вас недостаточно денег на счете. Пополните баланс!',
                             reply_markup=markup)

    await state.finish()
