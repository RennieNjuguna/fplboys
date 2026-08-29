from django.urls import path
from news import views

urlpatterns = [
    path('', views.gazette_view, name='gazette'),
    path('delete/<int:edition_id>/', views.delete_gazette_edition_view, name='delete_gazette_edition'),
    path('api/edition/<int:edition_num>/', views.api_gazette_data, name='api_gazette_data'),
]

