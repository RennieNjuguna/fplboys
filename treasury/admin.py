from django.contrib import admin
from django.utils.html import format_html
from treasury.models import Payment, AuditLog


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'member',
        'gameweek',
        'display_amount',
        'display_late_badge',
        'display_late_fine',
        'mpesa_code',
        'timestamp_received',
        'verified',
    )
    list_filter = ('gameweek', 'is_late', 'verified')
    search_fields = ('member__manager_name', 'member__team_name', 'mpesa_code', 'notes')
    date_hierarchy = 'timestamp_received'

    def display_amount(self, obj):
        return f"Ksh. {obj.amount_paid:,.2f}"
    display_amount.short_description = "Amount"

    def display_late_badge(self, obj):
        if obj.is_late:
            return format_html(
                '<span style="background-color: #d97706; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">LATE (+50 BBQ)</span>'
            )
        return format_html(
            '<span style="background-color: #059669; color: white; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">ON TIME</span>'
        )
    display_late_badge.short_description = "Status"

    def display_late_fine(self, obj):
        if obj.is_late and obj.late_fine_amount > 0:
            return format_html(
                '<span style="color: #d97706; font-weight: bold;">Ksh. {:,.2f}</span>',
                obj.late_fine_amount
            )
        return "-"
    display_late_fine.short_description = "Late Fine"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'description', 'performed_by')
    list_filter = ('action', 'performed_by')
    search_fields = ('description', 'performed_by')
    readonly_fields = ('action', 'description', 'performed_by', 'created_at')
