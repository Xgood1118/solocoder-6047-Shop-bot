
import re
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ContentType, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.callback_data import CallbackData
from keyboards.default.markups import *
from states import ProductState, CategoryState
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types.chat import ChatActions
from handlers.user.menu import settings
from loader import dp, db, bot
from filters import IsAdmin
from hashlib import md5


class BulkPriceState(StatesGroup):
    waiting_percentage = State()


category_cb = CallbackData('category', 'id', 'action')
product_cb = CallbackData('product', 'id', 'action')
select_product_cb = CallbackData('select_product', 'product_id', 'action')
bulk_price_cb = CallbackData('bulk_price', 'action')

add_product = '➕ Добавить товар'
delete_category = '🗑️ Удалить категорию'
bulk_price_change = '💰 Изменить цены'
finish_selection = '✅ Завершить выбор'
cancel_bulk = '🚫 Отменить'


@dp.message_handler(IsAdmin(), text=settings)
async def process_settings(message: Message):

    markup = InlineKeyboardMarkup()

    for idx, title in db.fetchall('SELECT * FROM categories'):

        markup.add(InlineKeyboardButton(
            title, callback_data=category_cb.new(id=idx, action='view')))

    markup.add(InlineKeyboardButton(
        '+ Добавить категорию', callback_data='add_category'))

    await message.answer('Настройка категорий:', reply_markup=markup)


@dp.callback_query_handler(IsAdmin(), category_cb.filter(action='view'))
async def category_callback_handler(query: CallbackQuery, callback_data: dict, state: FSMContext):

    category_idx = callback_data['id']

    products = db.fetchall('''SELECT * FROM products product
    WHERE product.tag = (SELECT title FROM categories WHERE idx=?)''',
                           (category_idx,))

    await query.message.delete()
    await query.answer('Все добавленные товары в эту категорию.')
    await state.update_data(category_index=category_idx)
    await state.update_data(selected_products=[])
    await state.update_data(bulk_mode=False)
    await show_products(query.message, products, category_idx, state)


async def check_admin_category_permission(admin_id, category_idx):
    any_restriction = db.fetchone('SELECT 1 FROM admin_categories WHERE category_idx = ?', (category_idx,))
    if not any_restriction:
        return True
    result = db.fetchone('SELECT 1 FROM admin_categories WHERE admin_id = ? AND category_idx = ?',
                         (admin_id, category_idx))
    return result is not None


@dp.callback_query_handler(IsAdmin(), select_product_cb.filter(action='toggle'))
async def toggle_product_selection(query: CallbackQuery, callback_data: dict, state: FSMContext):
    product_id = callback_data['product_id']

    async with state.proxy() as data:
        selected = data.get('selected_products', [])
        if product_id in selected:
            selected.remove(product_id)
        else:
            selected.append(product_id)
        data['selected_products'] = selected

    category_idx = None
    async with state.proxy() as data:
        category_idx = data.get('category_index')

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_idx,))
    category_title = category_title[0] if category_title else ''

    products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    await show_products(query.message, products, category_idx, state, edit_last=True)
    await query.answer(f'Выбрано товаров: {len(selected)}')


@dp.callback_query_handler(IsAdmin(), bulk_price_cb.filter(action='start'))
async def start_bulk_price_mode(query: CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['bulk_mode'] = True
        category_idx = data.get('category_index')

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_idx,))
    category_title = category_title[0] if category_title else ''

    products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    await query.answer('Режим массового изменения цен включен.')
    await show_products(query.message, products, category_idx, state, edit_last=True)


@dp.callback_query_handler(IsAdmin(), bulk_price_cb.filter(action='finish'))
async def finish_selection_handler(query: CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        selected = data.get('selected_products', [])
        category_idx = data.get('category_index')

    if len(selected) == 0:
        await query.answer('Выберите хотя бы один товар!', show_alert=True)
        return

    if not await check_admin_category_permission(query.from_user.id, category_idx):
        await query.answer('У вас нет доступа к этой категории!', show_alert=True)
        return

    await BulkPriceState.waiting_percentage.set()
    await query.message.answer(f'Выбрано товаров: <b>{len(selected)}</b>\n\n'
                               f'Введите процент изменения цены (например: 10.50 или -5.25):\n'
                               f'• Положительное значение - повышение цены\n'
                               f'• Отрицательное значение - понижение цены',
                               reply_markup=back_markup())


@dp.callback_query_handler(IsAdmin(), bulk_price_cb.filter(action='cancel'))
async def cancel_bulk_mode_handler(query: CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['bulk_mode'] = False
        data['selected_products'] = []
        category_idx = data.get('category_index')

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_idx,))
    category_title = category_title[0] if category_title else ''

    products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    await query.answer('Массовое изменение цен отменено.')
    await show_products(query.message, products, category_idx, state, edit_last=True)


@dp.message_handler(IsAdmin(), text=back_message, state=BulkPriceState.waiting_percentage)
async def cancel_bulk_price(message: Message, state: FSMContext):
    await state.finish()
    async with state.proxy() as data:
        data['bulk_mode'] = False
        data['selected_products'] = []
        category_idx = data.get('category_index')

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_idx,))
    category_title = category_title[0] if category_title else ''

    products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    await message.answer('Массовое изменение цен отменено.', reply_markup=ReplyKeyboardRemove())
    await show_products(message, products, category_idx, state)


@dp.message_handler(IsAdmin(), state=BulkPriceState.waiting_percentage)
async def process_percentage_input(message: Message, state: FSMContext):
    input_text = message.text.strip()

    if not re.match(r'^-?\d+(\.\d{1,2})?$', input_text):
        await message.answer('Неверный формат! Введите число с максимум двумя знаками после запятой.\nПримеры: 10, -5.5, 15.25')
        return

    percentage = float(input_text)

    if percentage == 0:
        await message.answer('Процент не может быть равен нулю!')
        return

    async with state.proxy() as data:
        selected_products = data.get('selected_products', [])
        category_idx = data.get('category_index')
        admin_id = message.from_user.id

    if not await check_admin_category_permission(admin_id, category_idx):
        await message.answer('У вас нет доступа к этой категории!', show_alert=True)
        await state.finish()
        return

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_idx,))
    category_title = category_title[0] if category_title else ''

    success_count = 0
    for product_id in selected_products:
        product = db.fetchone('SELECT * FROM products WHERE idx = ?', (product_id,))
        if not product:
            continue

        if product[5] != category_title:
            continue

        idx, title, body, image, old_price, tag = product
        new_price = int(round(old_price * (1 + percentage / 100)))

        if new_price < 0:
            new_price = 0

        db.query('UPDATE products SET price = ? WHERE idx = ?', (new_price, product_id))

        db.query('INSERT INTO price_history (product_idx, old_price, new_price, percentage, admin_id) VALUES (?, ?, ?, ?, ?)',
                 (product_id, old_price, new_price, percentage, admin_id))

        success_count += 1

    await state.finish()
    async with state.proxy() as data:
        data['bulk_mode'] = False
        data['selected_products'] = []

    products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    await message.answer(f'✅ Цены успешно изменены!\n\n'
                         f'Обработано товаров: <b>{success_count}</b>\n'
                         f'Процент изменения: <b>{percentage:+.2f}%</b>',
                         reply_markup=ReplyKeyboardRemove())

    await show_products(message, products, category_idx, state)


@dp.callback_query_handler(IsAdmin(), text='add_category')
async def add_category_callback_handler(query: CallbackQuery):
    await query.message.delete()
    await query.message.answer('Название категории?')
    await CategoryState.title.set()


@dp.message_handler(IsAdmin(), state=CategoryState.title)
async def set_category_title_handler(message: Message, state: FSMContext):

    category = message.text
    idx = md5(category.encode('utf-8')).hexdigest()
    db.query('INSERT INTO categories VALUES (?, ?)', (idx, category))

    db.query('INSERT INTO admin_categories VALUES (?, ?)', (message.from_user.id, idx))

    await state.finish()
    await process_settings(message)


@dp.message_handler(IsAdmin(), text=delete_category)
async def delete_category_handler(message: Message, state: FSMContext):

    async with state.proxy() as data:

        if 'category_index' in data.keys():

            idx = data['category_index']

            if not await check_admin_category_permission(message.from_user.id, idx):
                await message.answer('У вас нет доступа к этой категории!', show_alert=True)
                return

            db.query(
                'DELETE FROM products WHERE tag IN (SELECT title FROM categories WHERE idx=?)', (idx,))
            db.query('DELETE FROM categories WHERE idx=?', (idx,))
            db.query('DELETE FROM admin_categories WHERE category_idx=?', (idx,))

            await message.answer('Готово!', reply_markup=ReplyKeyboardRemove())
            await process_settings(message)


@dp.message_handler(IsAdmin(), text=add_product)
async def process_add_product(message: Message):

    await ProductState.title.set()

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(cancel_message)

    await message.answer('Название?', reply_markup=markup)


@dp.message_handler(IsAdmin(), text=cancel_message, state=ProductState.title)
async def process_cancel(message: Message, state: FSMContext):

    await message.answer('Ок, отменено!', reply_markup=ReplyKeyboardRemove())
    await state.finish()

    await process_settings(message)


@dp.message_handler(IsAdmin(), text=back_message, state=ProductState.title)
async def process_title_back(message: Message, state: FSMContext):
    await process_add_product(message)


@dp.message_handler(IsAdmin(), state=ProductState.title)
async def process_title(message: Message, state: FSMContext):

    async with state.proxy() as data:
        data['title'] = message.text

    await ProductState.next()
    await message.answer('Описание?', reply_markup=back_markup())


@dp.message_handler(IsAdmin(), text=back_message, state=ProductState.body)
async def process_body_back(message: Message, state: FSMContext):

    await ProductState.title.set()

    async with state.proxy() as data:

        await message.answer(f"Изменить название с <b>{data['title']}</b>?", reply_markup=back_markup())


@dp.message_handler(IsAdmin(), state=ProductState.body)
async def process_body(message: Message, state: FSMContext):

    async with state.proxy() as data:
        data['body'] = message.text

    await ProductState.next()
    await message.answer('Фото?', reply_markup=back_markup())


@dp.message_handler(IsAdmin(), content_types=ContentType.PHOTO, state=ProductState.image)
async def process_image_photo(message: Message, state: FSMContext):

    fileID = message.photo[-1].file_id
    file_info = await bot.get_file(fileID)
    downloaded_file = (await bot.download_file(file_info.file_path)).read()

    async with state.proxy() as data:
        data['image'] = downloaded_file

    await ProductState.next()
    await message.answer('Цена?', reply_markup=back_markup())


@dp.message_handler(IsAdmin(), content_types=ContentType.TEXT, state=ProductState.image)
async def process_image_url(message: Message, state: FSMContext):

    if message.text == back_message:

        await ProductState.body.set()

        async with state.proxy() as data:

            await message.answer(f"Изменить описание с <b>{data['body']}</b>?", reply_markup=back_markup())

    else:

        await message.answer('Вам нужно прислать фото товара.')


@dp.message_handler(IsAdmin(), lambda message: not message.text.isdigit(), state=ProductState.price)
async def process_price_invalid(message: Message, state: FSMContext):

    if message.text == back_message:

        await ProductState.image.set()

        async with state.proxy() as data:

            await message.answer("Другое изображение?", reply_markup=back_markup())

    else:

        await message.answer('Укажите цену в виде числа!')


@dp.message_handler(IsAdmin(), lambda message: message.text.isdigit(), state=ProductState.price)
async def process_price(message: Message, state: FSMContext):

    async with state.proxy() as data:

        data['price'] = message.text

        title = data['title']
        body = data['body']
        price = data['price']

        await ProductState.next()
        text = f'<b>{title}</b>\n\n{body}\n\nЦена: {price} рублей.'

        markup = check_markup()

        await message.answer_photo(photo=data['image'],
                                   caption=text,
                                   reply_markup=markup)


@dp.message_handler(IsAdmin(), lambda message: message.text not in [back_message, all_right_message], state=ProductState.confirm)
async def process_confirm_invalid(message: Message, state: FSMContext):
    await message.answer('Такого варианта не было.')


@dp.message_handler(IsAdmin(), text=back_message, state=ProductState.confirm)
async def process_confirm_back(message: Message, state: FSMContext):

    await ProductState.price.set()

    async with state.proxy() as data:

        await message.answer(f"Изменить цену с <b>{data['price']}</b>?", reply_markup=back_markup())


@dp.message_handler(IsAdmin(), text=all_right_message, state=ProductState.confirm)
async def process_confirm(message: Message, state: FSMContext):

    async with state.proxy() as data:

        title = data['title']
        body = data['body']
        image = data['image']
        price = data['price']

        tag = db.fetchone(
            'SELECT title FROM categories WHERE idx=?', (data['category_index'],))[0]
        idx = md5(' '.join([title, body, price, tag]
                           ).encode('utf-8')).hexdigest()

        db.query('INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)',
                 (idx, title, body, image, int(price), tag))

    await state.finish()
    await message.answer('Готово!', reply_markup=ReplyKeyboardRemove())
    await process_settings(message)


@dp.callback_query_handler(IsAdmin(), product_cb.filter(action='delete'))
async def delete_product_callback_handler(query: CallbackQuery, callback_data: dict, state: FSMContext):

    product_idx = callback_data['id']

    async with state.proxy() as data:
        category_idx = data.get('category_index')

    if category_idx and not await check_admin_category_permission(query.from_user.id, category_idx):
        await query.answer('У вас нет доступа к этой категории!', show_alert=True)
        return

    db.query('DELETE FROM products WHERE idx=?', (product_idx,))
    await query.answer('Удалено!')
    await query.message.delete()


async def show_products(m, products, category_idx, state, edit_last=False):

    await bot.send_chat_action(m.chat.id, ChatActions.TYPING)

    async with state.proxy() as data:
        bulk_mode = data.get('bulk_mode', False)
        selected_products = data.get('selected_products', [])

    for idx, title, body, image, price, tag in products:

        text = f'<b>{title}</b>\n\n{body}\n\nЦена: {price} рублей.'

        markup = InlineKeyboardMarkup()

        if bulk_mode:
            is_selected = idx in selected_products
            checkbox = '☑️' if is_selected else '⬜️'
            markup.add(InlineKeyboardButton(
                f'{checkbox} Выбрать', callback_data=select_product_cb.new(product_id=idx, action='toggle')))
        else:
            markup.add(InlineKeyboardButton(
                '🗑️ Удалить', callback_data=product_cb.new(id=idx, action='delete')))

        await m.answer_photo(photo=image,
                             caption=text,
                             reply_markup=markup)

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    if bulk_mode:
        markup.row(finish_selection, cancel_bulk)
        await m.answer(f'📋 Выбрано товаров: <b>{len(selected_products)}</b>\n\n'
                       'Нажмите на товары для выбора, затем нажмите "Завершить выбор".',
                       reply_markup=markup)
    else:
        markup.add(add_product)
        markup.add(delete_category)
        if len(products) > 0:
            markup.add(bulk_price_change)
        await m.answer('Хотите что-нибудь добавить или удалить?', reply_markup=markup)


@dp.message_handler(IsAdmin(), text=bulk_price_change)
async def process_bulk_price_change(message: Message, state: FSMContext):
    async with state.proxy() as data:
        category_idx = data.get('category_index')

    if not category_idx:
        await message.answer('Сначала выберите категорию!')
        return

    if not await check_admin_category_permission(message.from_user.id, category_idx):
        await message.answer('У вас нет доступа к этой категории!', show_alert=True)
        return

    async with state.proxy() as data:
        data['bulk_mode'] = True
        data['selected_products'] = []

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_idx,))
    category_title = category_title[0] if category_title else ''

    products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    if len(products) == 0:
        await message.answer('В этой категории нет товаров!')
        return

    await show_products(message, products, category_idx, state)


@dp.message_handler(IsAdmin(), text=finish_selection)
async def process_finish_selection(message: Message, state: FSMContext):
    async with state.proxy() as data:
        selected = data.get('selected_products', [])
        category_idx = data.get('category_index')

    if len(selected) == 0:
        await message.answer('Выберите хотя бы один товар!', show_alert=True)
        return

    if not await check_admin_category_permission(message.from_user.id, category_idx):
        await message.answer('У вас нет доступа к этой категории!', show_alert=True)
        return

    await BulkPriceState.waiting_percentage.set()
    await message.answer(f'Выбрано товаров: <b>{len(selected)}</b>\n\n'
                         f'Введите процент изменения цены (например: 10.50 или -5.25):\n'
                         f'• Положительное значение - повышение цены\n'
                         f'• Отрицательное значение - понижение цены',
                         reply_markup=back_markup())


@dp.message_handler(IsAdmin(), text=cancel_bulk)
async def process_cancel_bulk(message: Message, state: FSMContext):
    async with state.proxy() as data:
        data['bulk_mode'] = False
        data['selected_products'] = []
        category_idx = data.get('category_index')

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_idx,))
    category_title = category_title[0] if category_title else ''

    products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    await message.answer('Массовое изменение цен отменено.')
    await show_products(message, products, category_idx, state)
