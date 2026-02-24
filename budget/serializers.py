from rest_framework import serializers
from .models import Category, MonthlyBudget, Allocation

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "default_amount")


class AllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allocation
        fields = ("id", "category_name", "amount")


class MonthlyBudgetSerializer(serializers.ModelSerializer):
    allocations = AllocationSerializer(many=True, read_only=True)

    class Meta:
        model = MonthlyBudget
        fields = ("id", "month", "pay_date", "income", "allocations")