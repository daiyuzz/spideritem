from django.db import models

# Create your models here.

#创建一个存放url的表

class Spider_url(models.Model):
    url = models.CharField(max_length=200)