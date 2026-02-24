from django.db import models
from django.conf import settings

class Category(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=50)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.user.email} - {self.name}"


class MonthlyBudget(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monthly_budgets")
    month = models.DateField()  # store as first day of month (e.g., 2026-02-01)
    pay_date = models.DateField(null=True, blank=True)
    income = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "month")

    def __str__(self):
        return f"{self.user.email} - {self.month}"


class Allocation(models.Model):
    monthly_budget = models.ForeignKey(MonthlyBudget, on_delete=models.CASCADE, related_name="allocations")
    category_name = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.monthly_budget.user.email} - {self.category_name} - {self.amount}"