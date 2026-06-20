
import logging
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher.filters.state import StatesGroup, State
from keyboards.inline.categories import categories_markup, category_cb
from keyboards.inline.products_from_catalog import product_markup, product_cb
from aiogram.utils.callback_data import CallbackData
from aiogram.types.chat import ChatActions
from loader import dp, db, bot
from .menu import catalog
from filters import IsUser
from keyboards.default.markups import back_message


class CatalogSearchState(StatesGroup):
    viewing_category = State()
    search_mode = State()


search_cb = CallbackData('search', 'action')


@dp.message_handler(IsUser(), text=catalog)
async def process_catalog(message: Message, state: FSMContext):
    await state.finish()
    await message.answer('Выберите раздел, чтобы вывести список товаров:',
                         reply_markup=categories_markup())


@dp.callback_query_handler(IsUser(), category_cb.filter(action='view'))
async def category_callback_handler(query: CallbackQuery, callback_data: dict, state: FSMContext):

    category_id = callback_data['id']
    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_id,))
    category_title = category_title[0] if category_title else 'Категория'

    await CatalogSearchState.viewing_category.set()
    async with state.proxy() as data:
        data['current_category'] = category_id
        data['search_term'] = None

    products = db.fetchall('''SELECT * FROM products product
    WHERE product.tag = ?''',
                           (category_title,))

    await query.answer('Все доступные товары.')
    await show_products(query.message, products, query.message.chat.id, state)
    await query.message.answer('💡 Вы можете ввести ключевое слово для поиска товаров в этой категории.')


@dp.message_handler(IsUser(), state=CatalogSearchState.viewing_category)
async def process_search_input(message: Message, state: FSMContext):
    search_term = message.text.strip()

    if len(search_term) < 2:
        await message.answer('Введите поисковый запрос длиной не менее 2 символов.')
        return

    async with state.proxy() as data:
        data['search_term'] = search_term
        category_id = data['current_category']

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_id,))
    category_title = category_title[0] if category_title else ''

    all_products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    search_lower = search_term.lower()
    products = []
    for product in all_products:
        title = product[1] or ''
        body = product[2] or ''
        if search_lower in title.lower() or search_lower in body.lower():
            products.append(product)

    await message.answer(f'🔍 Результаты поиска по запросу: <b>{search_term}</b>')
    await show_products(message, products, message.chat.id, state)


@dp.callback_query_handler(IsUser(), search_cb.filter(action='clear'))
async def clear_search_handler(query: CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        data['search_term'] = None
        category_id = data['current_category']

    category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_id,))
    category_title = category_title[0] if category_title else ''

    products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

    await query.answer('Поиск очищен.')
    await show_products(query.message, products, query.message.chat.id, state)


@dp.callback_query_handler(IsUser(), search_cb.filter(action='back'))
async def back_to_categories_handler(query: CallbackQuery, state: FSMContext):
    await state.finish()
    await query.message.delete()
    await process_catalog(query.message, state)


@dp.callback_query_handler(IsUser(), product_cb.filter(action='add'))
async def add_product_callback_handler(query: CallbackQuery, callback_data: dict, state: FSMContext):

    current_state = await state.get_state()
    cid = query.message.chat.id
    product_id = callback_data['id']

    existing = db.fetchone('SELECT quantity FROM cart WHERE cid=? AND idx=?', (cid, product_id))
    if existing:
        db.query('UPDATE cart SET quantity = quantity + 1 WHERE cid=? AND idx=?', (cid, product_id))
    else:
        db.query('INSERT INTO cart VALUES (?, ?, 1)', (cid, product_id))

    await query.answer('Товар добавлен в корзину!')
    await query.message.delete()

    if current_state and 'CatalogSearchState' in current_state:
        async with state.proxy() as data:
            search_term = data.get('search_term')
            category_id = data.get('current_category')

        if search_term:
            category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_id,))
            category_title = category_title[0] if category_title else ''

            all_products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))
            search_lower = search_term.lower()
            products = []
            for product in all_products:
                title = product[1] or ''
                body = product[2] or ''
                if search_lower in title.lower() or search_lower in body.lower():
                    products.append(product)

            await show_products(query.message, products, cid, state)
        else:
            category_title = db.fetchone('SELECT title FROM categories WHERE idx=?', (category_id,))
            category_title = category_title[0] if category_title else ''

            products = db.fetchall('''SELECT * FROM products WHERE tag = ?''', (category_title,))

            await show_products(query.message, products, cid, state)


async def show_products(m, products, cid, state):

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    if len(products) == 0:
        async with state.proxy() as data:
            search_term = data.get('search_term')

        if search_term:
            text = f'😢 По запросу <b>{search_term}</b> ничего не найдено.\n\nПопробуйте изменить поисковый запрос или очистите поиск.'
        else:
            text = 'Здесь ничего нет 😢'

        markup = InlineKeyboardMarkup()
        if search_term:
            markup.add(InlineKeyboardButton('🔄 Очистить поиск', callback_data=search_cb.new(action='clear')))
        markup.add(InlineKeyboardButton('👈 Назад к категориям', callback_data=search_cb.new(action='back')))

        await m.answer(text, reply_markup=markup)

    else:
        await bot.send_chat_action(m.chat.id, ChatActions.TYPING)

        cart_items = db.fetchall('SELECT idx, quantity FROM cart WHERE cid=?', (cid,))
        cart_dict = {idx: quantity for idx, quantity in cart_items}

        products_by_category = {}
        for product in products:
            idx, title, body, image, price, tag = product
            if tag not in products_by_category:
                products_by_category[tag] = []
            products_by_category[tag].append(product)

        async with state.proxy() as data:
            search_term = data.get('search_term')

        for category_tag, category_products in products_by_category.items():
            if len(products_by_category) > 1:
                await m.answer(f'📁 <b>{category_tag}</b>')

            for idx, title, body, image, price, _ in category_products:
                quantity_in_cart = cart_dict.get(idx, 0)
                markup = product_markup(idx, price, quantity_in_cart)
                text = f'<b>{title}</b>\n\n{body}'

                await m.answer_photo(photo=image,
                                     caption=text,
                                     reply_markup=markup)

        markup = InlineKeyboardMarkup()
        if search_term:
            markup.add(InlineKeyboardButton('🔄 Очистить поиск', callback_data=search_cb.new(action='clear')))
        markup.add(InlineKeyboardButton('👈 Назад к категориям', callback_data=search_cb.new(action='back')))

        await m.answer('Действия:', reply_markup=markup)
