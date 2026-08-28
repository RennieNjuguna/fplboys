from django.contrib import admin
from django.utils.html import format_html
from league.models import Member, Gameweek, GameweekResult
from league.services.payout_engine import calculate_gameweek_payouts


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        'manager_name',
        'team_name',
        'fpl_entry_id',
        'phone_number',
        'display_overall_points',
        'display_prizes_won',
        'display_net_pl',
        'is_active'
    )
    search_fields = ('manager_name', 'team_name', 'fpl_entry_id', 'phone_number')
    list_filter = ('is_active',)

    def display_overall_points(self, obj):
        return f"{obj.total_overall_points} pts"
    display_overall_points.short_description = "Total Points"

    def display_prizes_won(self, obj):
        return format_html(
            '<span style="color: #059669; font-weight: bold;">Ksh. {:,.2f}</span>',
            obj.total_prizes_won
        )
    display_prizes_won.short_description = "Prizes Won"

    def display_net_pl(self, obj):
        net = obj.net_profit_loss
        color = "#059669" if net >= 0 else "#dc2626"
        sign = "+" if net > 0 else ""
        return format_html(
            f'<span style="color: {color}; font-weight: bold;">{sign}Ksh. {net:,.2f}</span>'
        )
    display_net_pl.short_description = "Net P/L"


@admin.register(Gameweek)
class GameweekAdmin(admin.ModelAdmin):
    list_display = (
        'number',
        'name',
        'display_deadline_eat',
        'display_status',
        'is_current',
        'is_next',
        'payout_calculated',
        'prize_pool_amount'
    )
    list_filter = ('status', 'is_current', 'is_next', 'month', 'payout_calculated')
    search_fields = ('name', 'number')
    actions = ['action_calculate_payouts']

    def display_deadline_eat(self, obj):
        if obj.deadline_eat:
            return obj.deadline_eat.strftime('%b %d, %Y %I:%M %p EAT')
        return "-"
    display_deadline_eat.short_description = "Deadline (EAT)"

    def display_status(self, obj):
        colors = {
            'finished': '#059669',  # Green
            'active': '#d97706',    # Amber
            'upcoming': '#6b7280',  # Gray
        }
        color = colors.get(obj.status, '#374151')
        return format_html(
            f'<span style="background-color: {color}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 11px;">{obj.status}</span>'
        )
    display_status.short_description = "Status"

    def action_calculate_payouts(self, request, queryset):
        count = 0
        for gw in queryset:
            calculate_gameweek_payouts(gw)
            count += 1
        self.message_user(request, f"Successfully calculated/recalculated payouts for {count} gameweeks.")
    action_calculate_payouts.short_description = "Calculate Top 3 Payouts & Tie-Breakers"


@admin.register(GameweekResult)
class GameweekResultAdmin(admin.ModelAdmin):
    list_display = (
        'gameweek',
        'member',
        'league_rank',
        'net_points',
        'gw_points',
        'transfer_cost',
        'display_prize_won',
        'is_top3',
        'overall_rank'
    )
    list_filter = ('gameweek', 'is_top3', 'league_rank')
    search_fields = ('member__manager_name', 'member__team_name', 'gameweek__name')

    def display_prize_won(self, obj):
        if obj.gw_prize_won > 0:
            return format_html(
                '<span style="color: #059669; font-weight: bold; background: #ecfdf5; padding: 2px 6px; border-radius: 4px;">Ksh. {:,.2f}</span>',
                obj.gw_prize_won
            )
        return "Ksh. 0.00"
    display_prize_won.short_description = "Prize Won"
