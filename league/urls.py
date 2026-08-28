from django.urls import path
from league import views

urlpatterns = [
    path('', views.dashboard_overview, name='dashboard'),
    path('standings/', views.standings_view, name='standings'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('manager/<int:member_id>/', views.manager_detail_view, name='manager_detail'),
    path('api/charts-data/', views.api_charts_data, name='api_charts_data'),
]
