from django.urls import path
from news import views

urlpatterns = [
    path('', views.gazette_view, name='gazette'),
    path('generate/', views.generate_gazette_action, name='generate_gazette'),
    path('api/edition/<int:edition_num>/', views.api_gazette_data, name='api_gazette_data'),
]

