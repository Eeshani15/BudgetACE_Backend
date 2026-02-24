from django.urls import path
from .views import (
    InitDefaultsView,
    UpdateCategoryDefaultsView,
    SetMonthlyIncomeView,
    GetMonthlySummaryView,
)

urlpatterns = [
    path("init-defaults/", InitDefaultsView.as_view()),
    path("update-defaults/", UpdateCategoryDefaultsView.as_view()),
    path("set-income/", SetMonthlyIncomeView.as_view()),
    path("summary/", GetMonthlySummaryView.as_view()),
]