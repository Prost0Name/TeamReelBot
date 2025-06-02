from tortoise.models import Model
from tortoise import fields

class Order(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    description = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "orders"

    def __str__(self):
        return self.title

class Task(Model):
    id = fields.IntField(pk=True)
    order = fields.ForeignKeyField('models.Order', related_name='tasks')
    user_id = fields.CharField(max_length=32)  # Telegram user id
    task_type = fields.CharField(max_length=32)  # Например: сценарий, озвучка и т.д.
    created_at = fields.DatetimeField(auto_now_add=True)
    # Добавляем поле статуса для отслеживания одобрения администратором
    status = fields.CharField(max_length=50, default='pending') # 'pending', 'approved', 'rejected'

    class Meta:
        table = "tasks"

    def __str__(self):
        return f"{self.task_type} для {self.order.title} ({self.user_id})"

class SubmittedFile(Model):
    id = fields.IntField(pk=True)
    task = fields.ForeignKeyField('models.Task', related_name='submitted_files')
    file_id = fields.CharField(max_length=255)
    file_type = fields.CharField(max_length=32) # 'document', 'photo', 'video'
    uploaded_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "submitted_files"

    def __str__(self):
        return f"{self.file_type} для задачи {self.task_id}"
