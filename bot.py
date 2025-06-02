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
from tortoise import fields, models
from datetime import datetime

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

# Новые состояния для процесса отклонения задачи администратором
class AdminRejectTaskForm(StatesGroup):
    reason = State()

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
    if str(message.from_user.id) not in ADMIN_ID:
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
    task_types = [
        ('script', 'Написание сценария'),
        ('voice', 'Озвучка'),
        ('edit', 'Монтаж'),
        ('preview', 'Создание превью'),
        ('upload', 'Отгрузка видео')
    ]
    
    task_buttons = []
    for key, text in task_types:
        # Проверяем, есть ли задача этого типа для данного заказа
        existing_task = await Task.filter(order_id=order_id, task_type=text).first()
        button_text = text
        if existing_task:
            button_text += " (Занято)"
        task_buttons.append(InlineKeyboardButton(text=button_text, callback_data=f"task_{key}_{order_id}"))

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
    # Получаем задачи пользователя, предварительно загружая информацию о проекте
    tasks = await Task.filter(user_id=user_id).prefetch_related('order')
    if not tasks:
        await message.reply("У вас нет активных задач")
        return
    
    # Группируем задачи по проектам и собираем информацию о статусе
    project_tasks_info = defaultdict(list) # {project_title: [(task_type, status)]}
    for task in tasks:
        project_tasks_info[task.order.title].append((task.task_type, task.status))
    
    text = "Ваши задачи:\n\n"
    for project, task_list in project_tasks_info.items():
        text += f"Проект: <b>{project}</b>\n"
        for task_type, status in task_list:
            status_text = ""
            if status == 'approved':
                status_text = " (Выполнено ✅)"
            elif status == 'rejected':
                status_text = " (Требуются доработки ❌)"
            # Для статуса 'pending' ничего не добавляем
                
            text += f"  - {task_type}{status_text}\n"
        text += "\n"
        
    await message.reply(text, parse_mode="HTML")

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
    # Получаем задачи пользователя, которые НЕ одобрены
    tasks = await Task.filter(user_id=user_id, status__not='approved').prefetch_related('order')

    if not tasks:
        await message.reply("У вас нет задач для сдачи работы (или все задачи уже одобрены).")
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
    
    # Кнопки для отправки на проверку и Назад
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отправить на проверку", callback_data="submit_confirm")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="submit_back_to_tasks")] # Кнопка Назад
        ]
    )

    await callback_query.message.edit_text(
        "Прикрепите файлы (можно несколько). После загрузки всех файлов нажмите 'Отправить на проверку'."
    )
    await callback_query.message.answer("Загрузите файлы, затем нажмите:", reply_markup=keyboard)
    await state.set_state(SubmitWorkForm.upload_files)

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

# Вспомогательная функция для отображения выполненных задач по проекту
async def display_completed_tasks_for_project(message, project_id):
    # Находим все задачи для этого проекта, у которых есть прикрепленные файлы
    tasks_with_files = await Task.filter(order_id=project_id, submitted_files__isnull=False).distinct().prefetch_related('order')
    
    if not tasks_with_files:
        await message.edit_text("В этом проекте нет выполненных задач с прикрепленными файлами.")
        return
    
    project_title = tasks_with_files[0].order.title # Название проекта одно для всех задач
    
    text = f"Задачи с прикрепленными файлами в проекте \"{project_title}\"\n\n"
    keyboard_buttons = []
    
    # Группируем задачи по типу и исполнителю (т.е. уникальные задачи)
    unique_tasks = defaultdict(dict) # {user_id: {task_type: task_object}}
    for task in tasks_with_files:
        unique_tasks[task.user_id][task.task_type] = task

    for user_id, tasks_by_type in unique_tasks.items():
        user_link = f"<a href=\"tg://user?id={user_id}\">{user_id}</a>"
        text += f"Исполнитель: {user_link}\n"
        for task_type, task in tasks_by_type.items():
            status_text = {
                'pending': 'Ожидает одобрения ⏳',
                'approved': 'Одобрено ✅',
                'rejected': 'Отклонено ❌'
            }.get(task.status, task.status) # Отображаем статус с эмодзи
            
            text += f"  - {task_type} ({status_text})\n"
            # Кнопка для просмотра файлов конкретной задачи пользователя
            keyboard_buttons.append(
                [InlineKeyboardButton(text=f"📂 Файлы {task_type} от {user_id}", callback_data=f"admin_view_task_files_{task.id}")]
            )
        text += "\n"
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад к проектам", callback_data="admin_completed_tasks_start")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("admin_completed_proj_"))
async def admin_completed_tasks_select_project(callback_query: CallbackQuery):
    project_id = int(callback_query.data.split("_")[-1])
    await display_completed_tasks_for_project(callback_query.message, project_id)

# НОВЫЙ ОБРАБОТЧИК для просмотра файлов конкретной задачи
@dp.callback_query(lambda c: c.data.startswith("admin_view_task_files_"))
async def admin_view_task_files(callback_query: CallbackQuery):
    task_id = int(callback_query.data.split("_")[-1])
    
    task = await Task.get(id=task_id).prefetch_related('submitted_files', 'order')
    
    if not task.submitted_files:
        await callback_query.answer("Для этой задачи нет прикрепленных файлов.", show_alert=True)
        # Вернуться к списку задач проекта
        await display_completed_tasks_for_project(callback_query.message, task.order.id) # Используем новую вспомогательную функцию
        return
        
    await callback_query.answer("Отправляю файлы задачи...", show_alert=True)
    
    media_group_items = []
    document_items = []
    
    project_title = task.order.title
    caption_text = f"Файлы для задачи \"{task.task_type}\" в проекте \"{project_title}\" от пользователя <a href=\"tg://user?id={task.user_id}\">{task.user_id}</a>"

    for file_info in task.submitted_files:
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
        
    # Кнопки Одобрить/Отклонить после отправки файлов
    approve_reject_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_task_{task.id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_task_{task.id}")]
        ]
    )
    await bot.send_message(callback_query.message.chat.id, "Выберите действие по этой задаче:", reply_markup=approve_reject_keyboard)

# НОВЫЙ ОБРАБОТЧИК для одобрения задачи
@dp.callback_query(lambda c: c.data.startswith("admin_approve_task_"))
async def admin_approve_task(callback_query: CallbackQuery):
    task_id = int(callback_query.data.split("_")[-1])
    
    task = await Task.get(id=task_id).prefetch_related('order')
    task.status = 'approved'
    # Также можно установить is_completed в True, если одобрение означает завершение
    task.is_completed = True
    await task.save()
    
    await callback_query.answer("Задача одобрена!", show_alert=True)
    
    # Опционально: отправить сообщение пользователю, что его задача одобрена
    try:
        await bot.send_message(int(task.user_id), f"✅ Ваша задача '{task.task_type}' в проекте '{task.order.title}' одобрена администратором.")
    except Exception as e:
        print(f"Не удалось отправить уведомление пользователю {task.user_id}: {e}")
        
    # Вернуться к списку задач проекта
    await display_completed_tasks_for_project(callback_query.message, task.order.id) # Используем новую вспомогательную функцию

# НОВЫЙ ОБРАБОТЧИК для отклонения задачи
@dp.callback_query(lambda c: c.data.startswith("admin_reject_task_"))
async def admin_reject_task(callback_query: CallbackQuery, state: FSMContext):
    task_id = int(callback_query.data.split("_")[-1])
    
    # Сохраняем ID задачи в состоянии для последующего использования
    await state.update_data(reject_task_id=task_id)
    
    # Добавляем кнопки "Пропустить" и "Назад"
    keyboard = InlineKeyboardButton(text="Пропустить", callback_data="admin_reject_skip")
    back_button = InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_reject_back_{task_id}")
    approve_reject_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [keyboard],
            [back_button]
        ]
    )
    
    await callback_query.message.edit_text(
        "Пожалуйста, введите причину отклонения задачи:",
        reply_markup=approve_reject_keyboard
    )
    await state.set_state(AdminRejectTaskForm.reason)

# НОВЫЙ ОБРАБОТЧИК для получения причины отклонения
@dp.message(AdminRejectTaskForm.reason)
async def process_reject_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('reject_task_id')
    reject_reason = message.text

    if not task_id:
        await message.reply("Произошла ошибка, не удалось определить задачу для отклонения.")
        await state.clear()
        return

    task = await Task.get(id=task_id).prefetch_related('order')
    task.status = 'rejected'
    task.is_completed = False # Отклоненная задача не считается выполненной
    await task.save()
    
    await message.reply("Причина отклонения принята. Задача отклонена.")

    # Отправить сообщение пользователю, что его задача отклонена, с указанием причины
    try:
        await bot.send_message(int(task.user_id), 
            f"❌ Ваша задача '{task.task_type}' в проекте '{task.order.title}' была отклонена администратором.\n\n"
            f"Причина: {reject_reason}\n\n"
            f"Пожалуйста, проверьте предоставленные файлы и внесите необходимые исправления." # Или другое указание
        )
    except Exception as e:
        print(f"Не удалось отправить уведомление пользователю {task.user_id}: {e}")
        
    await state.clear()
    
    # После отклонения и уведомления вернуться к списку задач проекта
    return_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Вернуться к задачам проекта", callback_data=f"admin_completed_proj_{task.order.id}")],
            [InlineKeyboardButton(text="⬅️ Вернуться в админ панель", callback_data="admin")]
        ]
    )
    await message.answer("Дальнейшие действия:", reply_markup=return_keyboard)

# НОВЫЙ ОБРАБОТЧИК для кнопки "Пропустить" при отклонении
@dp.callback_query(lambda c: c.data == "admin_reject_skip", AdminRejectTaskForm.reason)
async def admin_reject_skip(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    task_id = data.get('reject_task_id')

    if not task_id:
        await callback_query.message.edit_text("Произошла ошибка, не удалось определить задачу для отклонения.")
        await state.clear()
        return
    
    task = await Task.get(id=task_id).prefetch_related('order')
    task.status = 'rejected'
    task.is_completed = False
    await task.save()
    
    await callback_query.message.edit_text("Причина не указана. Задача отклонена.")

    # Отправить стандартное сообщение пользователю об отклонении
    try:
        await bot.send_message(int(task.user_id), f"❌ Ваша задача '{task.task_type}' в проекте '{task.order.title}' была отклонена администратором. Пожалуйста, проверьте предоставленные файлы.")
    except Exception as e:
        print(f"Не удалось отправить уведомление пользователю {task.user_id}: {e}")
        
    await state.clear()
    
    # Вернуться к списку задач проекта
    return_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Вернуться к задачам проекта", callback_data=f"admin_completed_proj_{task.order.id}")],
            [InlineKeyboardButton(text="⬅️ Вернуться в админ панель", callback_data="admin")]
        ]
    )
    await callback_query.message.answer("Дальнейшие действия:", reply_markup=return_keyboard)

# НОВЫЙ ОБРАБОТЧИК для кнопки "Назад" при загрузке файлов
@dp.callback_query(lambda c: c.data == "submit_back_to_tasks", SubmitWorkForm.upload_files)
async def submit_back_to_tasks(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    project_id = data.get('selected_project')
    tasks = data.get('tasks') # Получаем список задач из сохраненных данных

    if not project_id or not tasks:
        await callback_query.message.edit_text("Произошла ошибка при возврате. Пожалуйста, начните заново через 'Сдать работу'.")
        await state.clear()
        await callback_query.answer()
        return

    user_tasks = [t for t in tasks if t['order_id'] == project_id]
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t['task_type'], callback_data=f"submit_task_{t['id']}")]
            for t in user_tasks
        ]
    )
    
    await callback_query.message.edit_text("Выберите задачу:", reply_markup=keyboard)
    await state.set_state(SubmitWorkForm.select_task) # Возвращаемся в состояние выбора задачи
    await callback_query.answer() # Закрываем уведомление о нажатии кнопки

async def start_bot():
    await setup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_bot())