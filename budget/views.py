from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Category, MonthlyBudget, Allocation
from .serializers import CategorySerializer, MonthlyBudgetSerializer

User = get_user_model()


def first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def parse_month(month_str: str) -> date:
    # month_str like "2026-02"
    y, m = month_str.split("-")
    return date(int(y), int(m), 1)


DEFAULT_CATEGORIES = [
    ("Rent", Decimal("0")),
    ("Groceries", Decimal("0")),
    ("Bills", Decimal("0")),
    ("Savings", Decimal("0")),
    ("Transport", Decimal("0")),
    ("Entertainment", Decimal("0")),
]


class InitDefaultsView(APIView):
    """
    POST body: { "email": "user@email.com" }
    Creates default categories if user has none.
    """
    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        existing = Category.objects.filter(user=user).count()
        if existing == 0:
            for name, amt in DEFAULT_CATEGORIES:
                Category.objects.create(user=user, name=name, default_amount=amt)

        cats = Category.objects.filter(user=user).order_by("id")
        return Response({"categories": CategorySerializer(cats, many=True).data})


class UpdateCategoryDefaultsView(APIView):
    """
    POST body:
    {
      "email": "user@email.com",
      "categories": [
        {"name":"Rent","default_amount": 800},
        {"name":"Groceries","default_amount": 250}
      ]
    }
    Upserts category defaults.
    """
    @transaction.atomic
    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        categories = request.data.get("categories", [])

        if not email:
            return Response({"error": "email is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(categories, list):
            return Response({"error": "categories must be a list"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        for c in categories:
            name = str(c.get("name", "")).strip()
            if not name:
                continue
            amt = Decimal(str(c.get("default_amount", "0")))
            obj, _ = Category.objects.get_or_create(user=user, name=name)
            obj.default_amount = amt
            obj.save()

        cats = Category.objects.filter(user=user).order_by("id")
        return Response({"categories": CategorySerializer(cats, many=True).data})


class SetMonthlyIncomeView(APIView):
    """
    POST body:
    {
      "email": "user@email.com",
      "month": "2026-02",
      "pay_date": "2026-02-02",
      "income": 500
    }

    Creates/updates MonthlyBudget and auto-allocates based on Category defaults.
    Returns remaining + percentages + improvement vs last month (only if last month exists).
    """
    @transaction.atomic
    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        month_str = str(request.data.get("month", "")).strip()
        pay_date_str = str(request.data.get("pay_date", "")).strip()
        income_raw = request.data.get("income", 0)

        if not email or not month_str:
            return Response({"error": "email and month are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        month = parse_month(month_str)
        income = Decimal(str(income_raw))

        pay_date = None
        if pay_date_str:
            y, m, d = pay_date_str.split("-")
            pay_date = date(int(y), int(m), int(d))

        mb, _ = MonthlyBudget.objects.get_or_create(user=user, month=month)
        mb.income = income
        mb.pay_date = pay_date
        mb.save()

        # Ensure categories exist
        if Category.objects.filter(user=user).count() == 0:
            for name, amt in DEFAULT_CATEGORIES:
                Category.objects.create(user=user, name=name, default_amount=amt)

        # Rebuild allocations from defaults
        Allocation.objects.filter(monthly_budget=mb).delete()

        cats = Category.objects.filter(user=user).order_by("id")
        allocated_total = Decimal("0")

        for c in cats:
            amt = Decimal(c.default_amount or 0)
            # Don’t allocate more than remaining income
            remaining_for_alloc = income - allocated_total
            use_amt = amt if amt <= remaining_for_alloc else max(Decimal("0"), remaining_for_alloc)

            Allocation.objects.create(
                monthly_budget=mb,
                category_name=c.name,
                amount=use_amt
            )
            allocated_total += use_amt

        remaining = income - allocated_total if income >= allocated_total else Decimal("0")

        # Percentages
        allocations = mb.allocations.all()
        alloc_list = []
        for a in allocations:
            pct = Decimal("0")
            if income > 0:
                pct = (Decimal(a.amount) / income) * Decimal("100")
            alloc_list.append({
                "category": a.category_name,
                "amount": float(a.amount),
                "percent": float(pct.quantize(Decimal("0.01"))),
            })

        # Improvement check (compare remaining % with previous month remaining %)
        prev_month = date(month.year - 1, 12, 1) if month.month == 1 else date(month.year, month.month - 1, 1)
        prev = MonthlyBudget.objects.filter(user=user, month=prev_month).first()

        improvement = None
        if prev and prev.income and prev.income > 0:
            prev_alloc_total = sum([x.amount for x in prev.allocations.all()], Decimal("0"))
            prev_remaining = (prev.income - prev_alloc_total) if prev.income >= prev_alloc_total else Decimal("0")
            prev_save_pct = (prev_remaining / prev.income) * Decimal("100")

            cur_save_pct = Decimal("0")
            if income > 0:
                cur_save_pct = (remaining / income) * Decimal("100")

            diff = cur_save_pct - prev_save_pct
            improvement = {
                "previous_month": prev_month.isoformat()[:7],
                "previous_saving_percent": float(prev_save_pct.quantize(Decimal("0.01"))),
                "current_month": month.isoformat()[:7],
                "current_saving_percent": float(cur_save_pct.quantize(Decimal("0.01"))),
                "difference_percent_points": float(diff.quantize(Decimal("0.01"))),
                "message": (
                    "✅ You are improving! Saving more than last month."
                    if diff > 0 else
                    "⚠️ You saved less than last month. Try reducing non-essentials."
                    if diff < 0 else
                    "➖ Same saving rate as last month."
                )
            }

        return Response({
            "month": month.isoformat()[:7],
            "pay_date": pay_date.isoformat() if pay_date else None,
            "income": float(income),
            "allocated_total": float(allocated_total),
            "remaining": float(remaining),
            "allocations": alloc_list,
            "improvement": improvement,  # null if first month
        })


class GetMonthlySummaryView(APIView):
    """
    GET /api/budget/summary/?email=...&month=2026-02
    """
    def get(self, request):
        email = str(request.query_params.get("email", "")).strip().lower()
        month_str = str(request.query_params.get("month", "")).strip()
        if not email or not month_str:
            return Response({"error": "email and month are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        month = parse_month(month_str)
        mb = MonthlyBudget.objects.filter(user=user, month=month).first()
        if not mb:
            return Response({"error": "No budget found for this month"}, status=status.HTTP_404_NOT_FOUND)

        return Response(MonthlyBudgetSerializer(mb).data)