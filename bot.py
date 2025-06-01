from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMIN_ID
from database.models import Order, Task
from database import setup
from collections import defaultdict

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class OrderForm(StatesGroup):
    title = State()
    description = State()

class ProjectForm(StatesGroup):
    title = State()
    description = State()

TASK_TYPE_MAP = {
    'script': 'Написание сценария',
    'voice': 'Озвучка',
    'edit': 'Монтаж',
    'preview': 'Создание превью',
    'upload': 'Отгрузка видео',
}

@dp.message(CommandStart())
async def cmd_start(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Проекты")], [KeyboardButton(text="Мои задачи")]],
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
            [InlineKeyboardButton(text="Новый заказ", callback_data="new_order")],
            [InlineKeyboardButton(text="Список задач пользователей", callback_data="admin_tasks")]
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
    
    # Кнопки задач
    task_buttons = [
        InlineKeyboardButton(text="Написание сценария", callback_data=f"task_script_{order_id}"),
        InlineKeyboardButton(text="Озвучка", callback_data=f"task_voice_{order_id}"),
        InlineKeyboardButton(text="Монтаж", callback_data=f"task_edit_{order_id}"),
        InlineKeyboardButton(text="Создание превью", callback_data=f"task_preview_{order_id}"),
        InlineKeyboardButton(text="Отгрузка видео", callback_data=f"task_upload_{order_id}")
    ]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [btn] for btn in task_buttons
        ] + [[InlineKeyboardButton(text="Назад", callback_data="back_to_projects")]]
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

@dp.callback_query(lambda c: c.data.startswith("task_"))
async def take_task(callback_query: CallbackQuery):
    parts = callback_query.data.split('_')
    task_type_key = parts[1]
    order_id = int(parts[2])
    user_id = str(callback_query.from_user.id)
    task_type = TASK_TYPE_MAP.get(task_type_key, task_type_key)

    # Проверяем, не взял ли уже кто-то эту задачу по этому заказу
    existing = await Task.filter(order_id=order_id, task_type=task_type).first()
    if existing:
        if existing.user_id == user_id:
            await callback_query.answer("Вы уже взялись за эту задачу", show_alert=True)
        else:
            await callback_query.answer("Эта задача уже занята другим пользователем", show_alert=True)
        return
    # Создаем задачу
    await Task.create(order_id=order_id, user_id=user_id, task_type=task_type)
    await callback_query.answer(f"Вы взялись за: {task_type}", show_alert=True)

@dp.message(lambda message: message.text == "Мои задачи")
async def my_tasks(message: Message):
    user_id = str(message.from_user.id)
    tasks = await Task.filter(user_id=user_id).prefetch_related('order')
    if not tasks:
        await message.reply("У вас нет активных задач")
        return
    text = "Ваши задачи:\n\n"
    for task in tasks:
        text += f"Проект: {task.order.title}\nЗадача: {task.task_type}\n\n"
    await message.reply(text)

@dp.callback_query(lambda c: c.data == "admin_tasks")
async def admin_tasks(callback_query: CallbackQuery):
    tasks = await Task.all().prefetch_related('order')
    if not tasks:
        await callback_query.message.edit_text("Нет активных задач пользователей")
        return
    # Группируем задачи по проектам и категориям
    project_tasks = defaultdict(list)
    for task in tasks:
        project_tasks[task.order.title].append((task.task_type, task.user_id))
    text = "Список задач пользователей:\n\n"
    for project, task_list in project_tasks.items():
        text += f"Проект: <b>{project}</b>\n"
        for task_type, user_id in task_list:
            text += f"{task_type}: <a href=\"tg://user?id={user_id}\">{user_id}</a>\n"
        text += "\n"
    await callback_query.message.edit_text(text, parse_mode="HTML")

async def start_bot():
    await setup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_bot())