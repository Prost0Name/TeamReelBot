from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMIN_ID
from database.models import Order
from database import setup

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class OrderForm(StatesGroup):
    title = State()
    description = State()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.reply("Привет! Я бот для управления заказами.")

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if str(message.from_user.id) != ADMIN_ID:
        await message.reply("У вас нет прав администратора")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Новый заказ", callback_data="new_order")]
        ]
    )
    await message.reply("Админ панель", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "new_order")
async def process_new_order(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите название заказа:")
    await state.set_state(OrderForm.title)

@dp.message(OrderForm.title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.reply("Введите описание заказа:")
    await state.set_state(OrderForm.description)

@dp.message(OrderForm.description)
async def process_description(message: Message, state: FSMContext):
    data = await state.get_data()
    
    order = await Order.create(
        title=data["title"],
        description=message.text
    )
    
    await message.reply(f"Заказ успешно создан!\n\nНазвание: {order.title}\nОписание: {order.description}")
    await state.clear()

async def start_bot():
    await setup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_bot())