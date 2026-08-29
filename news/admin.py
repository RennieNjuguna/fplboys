from django.contrib import admin
from news.models import RoastEdition, ManagerRoastItem


class ManagerRoastInline(admin.StackedInline):
    model = ManagerRoastItem
    extra = 0


@admin.register(RoastEdition)
class RoastEditionAdmin(admin.ModelAdmin):
    list_display = ('edition_number', 'gameweek', 'headline', 'clown_of_the_week', 'king_of_the_week', 'is_published', 'publish_date')
    list_filter = ('is_published', 'publish_date')
    search_fields = ('headline', 'editorial_lead', 'clown_reason', 'king_reason')
    inlines = [ManagerRoastInline]


@admin.register(ManagerRoastItem)
class ManagerRoastItemAdmin(admin.ModelAdmin):
    list_display = ('member', 'edition', 'rank_in_gw', 'net_points', 'badge', 'verdict')
    list_filter = ('edition', 'badge')
    search_fields = ('member__manager_name', 'roast_title', 'roast_body', 'verdict')
