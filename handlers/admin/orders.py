
import json
from aiogram.types import Message
from loader import dp, db
from handlers.user.menu import orders
from filters import IsAdmin

@dp.message_handler(IsAdmin(), text=orders)
async def process_orders(message: Message):
    
    orders = db.fetchall('SELECT rowid, cid, usr_name, usr_address, products, delivery_slot FROM orders')
    
    if len(orders) == 0: 
        await message.answer('У вас нет заказов.')
    else: 
        await order_answer(message, orders)

async def order_answer(message, orders):

    for order in orders:
        order_id, cid, usr_name, usr_address, products, delivery_slot_json = order
        
        res = f'📦 Заказ <b>№{order_id}</b>\n'
        res += f'👤 Имя: <b>{usr_name}</b>\n'
        res += f'📍 Адрес: <b>{usr_address}</b>\n'
        res += f'🛒 Товары: <b>{products}</b>\n'
        
        if delivery_slot_json:
            try:
                delivery_slot = json.loads(delivery_slot_json)
                res += f'🕐 Доставка: <b>{delivery_slot.get("name_ru", "")}</b> ({delivery_slot.get("time_range", "")})'
            except:
                pass
        
        res += '\n\n'
        await message.answer(res)