from django.urls import path
from treasury import views

urlpatterns = [
    path('unlock/', views.treasury_unlock_view, name='treasury_unlock'),
    path('lock/', views.treasury_lock_view, name='treasury_lock'),
    path('ledger/', views.financial_ledger_view, name='financial_ledger'),
    path('portal/', views.treasurer_portal_view, name='treasurer_portal'),
    path('payment/<int:payment_id>/edit/', views.payment_edit_view, name='payment_edit'),
    path('payment/<int:payment_id>/delete/', views.payment_delete_view, name='payment_delete'),
    path('transaction/<int:transaction_id>/delete/', views.transaction_delete_view, name='transaction_delete'),
    path('payout/<int:payout_id>/delete/', views.payout_delete_view, name='payout_delete'),
    path('api/check-deadline/', views.api_check_deadline, name='api_check_deadline'),
]
