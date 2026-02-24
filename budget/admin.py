from django.contrib import admin
from .models import Category, MonthlyBudget, Allocation

admin.site.register(Category)
admin.site.register(MonthlyBudget)
admin.site.register(Allocation)