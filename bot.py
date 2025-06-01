from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, FSInputFile, BufferedInputFile, InputMediaDocument, InputMediaPhoto, InputMediaVideo
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMIN_ID
from database.models import Order, Task, SubmittedFile
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

class SubmitWorkForm(StatesGroup):
    select_project = State()
    select_task = State()
    upload_files = State()
    confirm = State()

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
        keyboard=[
            [KeyboardButton(text="📋 Проекты")],
            [KeyboardButton(text="📝 Мои задачи"), KeyboardButton(text="📤 Сдать работу")]
        ],
        resize_keyboard=True
    )
    await message.reply(
        "Добро пожаловать в TeamReelBot!\n\nЯ помогу вам управлять проектами и заказами.\n\nДля администраторов доступна команда /admin",
        reply_markup=keyboard
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if str(message.from_user.id) != ADMIN_ID:
        await message.reply("У вас нет прав администратора")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Новый заказ", callback_data="new_order")],
            [InlineKeyboardButton(text="Список задач пользователей", callback_data="admin_tasks")],
            [InlineKeyboardButton(text="Выполненные задачи", callback_data="admin_completed_tasks_start")]
        ]
    )
    await message.reply("Админ панель", reply_markup=keyboard)

@dp.message(lambda message: message.text == "📋 Проекты")
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

@dp.message(lambda message: message.text == "📝 Мои задачи")
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

@dp.message(lambda message: message.text == "📤 Сдать работу")
async def submit_work_start(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    tasks = await Task.filter(user_id=user_id).prefetch_related('order')
    if not tasks:
        await message.reply("У вас нет задач для сдачи работы")
        return
    # Собираем уникальные проекты
    projects = {task.order.id: task.order.title for task in tasks}
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=title, callback_data=f"submit_proj_{proj_id}")]
            for proj_id, title in projects.items()
        ]
    )
    await message.reply("Выберите проект:", reply_markup=keyboard)
    await state.set_state(SubmitWorkForm.select_project)
    await state.update_data(tasks=[{'id': t.id, 'order_id': t.order.id, 'order_title': t.order.title, 'task_type': t.task_type} for t in tasks])

@dp.callback_query(lambda c: c.data.startswith("submit_proj_"), SubmitWorkForm.select_project)
async def submit_work_select_project(callback_query: CallbackQuery, state: FSMContext):
    project_id = int(callback_query.data.split("_")[-1])
    data = await state.get_data()
    user_tasks = [t for t in data['tasks'] if t['order_id'] == project_id]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t['task_type'], callback_data=f"submit_task_{t['id']}")]
            for t in user_tasks
        ]
    )
    await callback_query.message.edit_text("Выберите задачу:", reply_markup=keyboard)
    await state.set_state(SubmitWorkForm.select_task)
    await state.update_data(selected_project=project_id)

@dp.callback_query(lambda c: c.data.startswith("submit_task_"), SubmitWorkForm.select_task)
async def submit_work_select_task(callback_query: CallbackQuery, state: FSMContext):
    task_id = int(callback_query.data.split("_")[-1])
    await state.update_data(selected_task=task_id, files=[])
    await callback_query.message.edit_text("Прикрепите файлы (можно несколько). После загрузки всех файлов нажмите 'Отправить на проверку'.")
    await state.set_state(SubmitWorkForm.upload_files)
    # Кнопка для отправки на проверку
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отправить на проверку", callback_data="submit_confirm")]
        ]
    )
    await callback_query.message.answer("Загрузите файлы, затем нажмите:", reply_markup=keyboard)

@dp.message(SubmitWorkForm.upload_files, F.content_type.in_(["document", "photo", "video"]))
async def submit_work_upload_file(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get('files', [])
    file_info = None
    if message.document:
        file_info = {'file_id': message.document.file_id, 'type': 'document'}
    elif message.photo:
        # Для фото берем последний элемент из списка размеров, т.к. он самый большой
        file_info = {'file_id': message.photo[-1].file_id, 'type': 'photo'}
    elif message.video:
        file_info = {'file_id': message.video.file_id, 'type': 'video'}
    
    if file_info:
        files.append(file_info)
        await state.update_data(files=files)
        await message.reply("Файл добавлен. Можете добавить ещё или нажмите 'Отправить на проверку'.")
    else:
         # Это сообщение, скорее всего, не будет достигнуто из-за фильтра F, но на всякий случай.
         await message.reply("Пожалуйста, прикрепите документ, фото или видео.")

@dp.callback_query(lambda c: c.data == "submit_confirm", SubmitWorkForm.upload_files)
async def submit_work_confirm(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    files_to_save = data.get('files', [])
    task_id = data.get('selected_task')

    if not files_to_save:
        await callback_query.answer("Сначала прикрепите хотя бы один файл!", show_alert=True)
        return
    
    # Получаем объект задачи
    task = await Task.get(id=task_id)

    # Сохраняем информацию о файлах в базе данных
    saved_count = 0
    for file_info in files_to_save:
        # Проверяем, не был ли этот файл уже прикреплен к этой задаче
        existing_file = await SubmittedFile.filter(task=task, file_id=file_info['file_id']).first()
        if not existing_file:
            await SubmittedFile.create(
                task=task,
                file_id=file_info['file_id'],
                file_type=file_info['type']
            )
            saved_count += 1

    if saved_count > 0:
        await callback_query.message.edit_text(f"Работа ({saved_count} новых файл(а/ов)) прикреплена к задаче.\nОжидайте проверки администратором.")
    else:
         await callback_query.message.edit_text("Выбранные файлы уже были прикреплены к этой задаче.")
         
    await state.clear() # Очищаем состояние после сохранения

@dp.callback_query(lambda c: c.data == "admin_completed_tasks_start")
async def admin_completed_tasks_start(callback_query: CallbackQuery):
    # Находим все задачи, у которых есть прикрепленные файлы
    tasks_with_files = await Task.filter(submitted_files__isnull=False).distinct().prefetch_related('order')
    
    if not tasks_with_files:
        await callback_query.message.edit_text("Нет выполненных задач с прикрепленными файлами.")
        return
    
    # Группируем задачи по проектам
    projects = {}
    for task in tasks_with_files:
        if task.order.id not in projects:
            projects[task.order.id] = task.order.title
            
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=title, callback_data=f"admin_completed_proj_{proj_id}")]
            for proj_id, title in projects.items()
        ]
    )
    
    await callback_query.message.edit_text("Выберите проект для просмотра выполненных задач:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("admin_completed_proj_"))
async def admin_completed_tasks_select_project(callback_query: CallbackQuery):
    project_id = int(callback_query.data.split("_")[-1])
    
    # Находим все задачи для этого проекта, у которых есть прикрепленные файлы
    tasks_with_files = await Task.filter(order_id=project_id, submitted_files__isnull=False).prefetch_related('order')
    
    if not tasks_with_files:
        await callback_query.message.edit_text("В этом проекте нет выполненных задач с прикрепленными файлами.")
        return
    
    project_title = tasks_with_files[0].order.title # Название проекта одно для всех задач
    
    # Группируем задачи по типу (категории) и собираем исполнителей
    completed_task_info = defaultdict(set) # Используем set для уникальных user_id
    for task in tasks_with_files:
         completed_task_info[task.task_type].add(task.user_id)
    
    text = f"Выполненные категории задач в проекте \"{project_title}\"\n\n"
    keyboard_buttons = []
    
    for task_type, user_ids in completed_task_info.items():
        text += f"<b>{task_type}</b>\n"
        for user_id in user_ids:
             user_link = f"<a href=\"tg://user?id={user_id}\">{user_id}</a>"
             text += f"  Выполнил: {user_link}\n"
             
        # Callback data будет включать project_id и task_type
        keyboard_buttons.append(
            [InlineKeyboardButton(text=f"Получить файлы для: {task_type}", callback_data=f"admin_get_category_files_{project_id}_{task_type}")]
        )
        text += "\n"
    
    text += "\nДля просмотра файлов по категории нажмите соответствующую кнопку."
        
    keyboard_buttons.append([InlineKeyboardButton(text="Назад к проектам", callback_data="admin_completed_tasks_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

# Новый обработчик для получения файлов по категории
@dp.callback_query(lambda c: c.data.startswith("admin_get_category_files_"))
async def admin_get_category_files(callback_query: CallbackQuery):
    parts = callback_query.data.split("_")
    project_id = int(parts[-2])
    task_type = parts[-1]
    
    # Находим все задачи этого типа в проекте
    tasks_in_category = await Task.filter(order_id=project_id, task_type=task_type).prefetch_related('submitted_files')
    
    if not tasks_in_category:
        await callback_query.answer("Нет задач этой категории в проекте.", show_alert=True)
        return
        
    all_submitted_files = []
    for task in tasks_in_category:
        for submitted_file in task.submitted_files:
            all_submitted_files.append(submitted_file)
            
    if not all_submitted_files:
        await callback_query.answer("Для этой категории задач нет прикрепленных файлов.", show_alert=True)
        return
        
    await callback_query.answer("Отправляю файлы по категории...", show_alert=True)
    
    # Отправляем файлы. Сгруппируем фото и видео в медиа-группу, документы по одному.
    media_group_items = []
    document_items = []
    
    # Получим название проекта и тип задачи для подписи/описания
    project = await Order.get(id=project_id)
    caption_text = f"Файлы для категории \"{task_type}\" в проекте \"{project.title}\""

    for file_info in all_submitted_files:
        if file_info.file_type == 'photo':
            media_group_items.append(InputMediaPhoto(media=file_info.file_id))
        elif file_info.file_type == 'video':
            media_group_items.append(InputMediaVideo(media=file_info.file_id))
        elif file_info.file_type == 'document':
            document_items.append(file_info.file_id)

    # Отправляем медиа-группу
    if media_group_items:
        # Первому элементу медиа-группы можно добавить подпись
        media_group_items[0].caption = caption_text
        media_group_items[0].parse_mode = "HTML"
        await bot.send_media_group(callback_query.message.chat.id, media_group_items)
        
    # Отправляем документы отдельно
    for doc_file_id in document_items:
        await bot.send_document(callback_query.message.chat.id, doc_file_id) 
        
    # Можно отправить финальное сообщение после отправки всех файлов
    # await bot.send_message(callback_query.message.chat.id, "Все файлы отправлены по категории.")

async def start_bot():
    await setup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_bot())