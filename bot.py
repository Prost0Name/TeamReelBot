from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
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

class ProjectForm(StatesGroup):
    title = State()
    description = State()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Проекты")]],
        resize_keyboard=True
    )
    
    await message.reply("Добро пожаловать в TeamReelBot!\n\nЯ помогу вам управлять проектами и заказами.\n\nДля администраторов доступна команда /admin", reply_markup=keyboard)

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

@dp.message(lambda message: message.text == "Проекты")
async def show_projects(message: Message):
    orders = await Order.all()
    if not orders:
        await message.reply("Список проектов пуст")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=order.title, callback_data=f"order_{order.id}")] 
            for order in orders
        ]
    )
    
    await message.reply("Список проектов:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("order_"))
async def show_order_info(callback_query: CallbackQuery):
    order_id = int(callback_query.data.split("_")[1])
    order = await Order.get(id=order_id)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_projects")]
        ]
    )
    
    await callback_query.message.edit_text(
        f"Информация о проекте:\n\n"
        f"Название: {order.title}\n"
        f"Описание: {order.description}\n"
        f"Создан: {order.created_at.strftime('%d.%m.%Y')}",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "back_to_projects")
async def back_to_projects(callback_query: CallbackQuery):
    orders = await Order.all()
    if not orders:
        await callback_query.message.edit_text("Список проектов пуст")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=order.title, callback_data=f"order_{order.id}")] 
            for order in orders
        ]
    )
    
    await callback_query.message.edit_text("Список проектов:", reply_markup=keyboard)

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
    
    await message.reply(f"Проект успешно создан!\n\nНазвание: {order.title}\nОписание: {order.description}")
    await state.clear()

async def start_bot():
    await setup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_bot())