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

    class Meta:
        table = "tasks"

    def __str__(self):
        return f"{self.task_type} для {self.order.title} ({self.user_id})"
