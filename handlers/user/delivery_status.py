
import json
from aiogram.types import Message
from loader import dp, db
from .menu import delivery_status
from filters import IsUser

@dp.message_handler(IsUser(), text=delivery_status)
async def process_delivery_status(message: Message):
    
    orders = db.fetchall('SELECT rowid, cid, usr_name, usr_address, products, delivery_slot FROM orders WHERE cid=?', (message.chat.id,))
    
    if len(orders) == 0: 
        await message.answer('У вас нет активных заказов.')
    else: 
        await delivery_status_answer(message, orders)

async def delivery_status_answer(message, orders):

    for order in orders:
        order_id, cid, usr_name, usr_address, products_str, delivery_slot_json = order
        
        res = f'📦 Заказ <b>№{order_id}</b>\n'
        res += f'👤 Имя: <b>{usr_name}</b>\n'
        res += f'📍 Адрес: <b>{usr_address}</b>\n'
        res += f'🛒 Товары: <b>{products_str}</b>\n'
        
        if delivery_slot_json:
            try:
                delivery_slot = json.loads(delivery_slot_json)
                res += f'🕐 Доставка: <b>{delivery_slot.get("name_ru", "")}</b> ({delivery_slot.get("time_range", "")})\n'
            except:
                pass

        answer = [
            ' лежит на складе.',
            ' уже в пути!',
            ' прибыл и ждет вас на почте!'
        ]

        res += f'Статус: заказ{answer[0]}'

        await message.answer(res)
