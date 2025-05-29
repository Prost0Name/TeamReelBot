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
