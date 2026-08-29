from django.db import models
from django.utils import timezone
from league.models import Member, Gameweek


class RoastEdition(models.Model):
    gameweek = models.OneToOneField(
        Gameweek,
        on_delete=models.CASCADE,
        related_name='roast_edition',
        help_text='Associated gameweek for this newspaper edition'
    )
    edition_number = models.IntegerField(unique=True, help_text='Newspaper Issue # (typically matches GW number)')
    headline = models.CharField(max_length=255, default='THE WEEKLY FPL MASSACRE')
    subheadline = models.CharField(max_length=300, blank=True, default='')
    publish_date = models.DateTimeField(default=timezone.now)
    chief_editor = models.CharField(max_length=120, default='The League Scribe & Hater-in-Chief')
    weather_report = models.CharField(max_length=200, default='High pressure in the relegation zone, 100% chance of tears.')
    editorial_lead = models.TextField(help_text='Front-page main editorial breakdown of the gameweek')

    clown_of_the_week = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clown_editions'
    )
    clown_reason = models.TextField(blank=True, default='')

    king_of_the_week = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='king_editions'
    )
    king_reason = models.TextField(blank=True, default='')

    quote_of_the_week = models.TextField(blank=True, default='')
    quote_author = models.CharField(max_length=120, blank=True, default='Anonymous Benchwarmer')

    defaulter_roast = models.TextField(blank=True, default='', help_text='Roast dedicated to unpaid or late contributors')
    transfer_hit_roast = models.TextField(blank=True, default='', help_text='Roast for reckless -4 hits or bench blunders')
    classified_ads_raw = models.TextField(default='[]', blank=True, help_text='JSON encoded list of satirical classified ads')

    @property
    def classified_ads(self):
        import json
        try:
            return json.loads(self.classified_ads_raw)
        except Exception:
            return []

    @classified_ads.setter
    def classified_ads(self, value):
        import json
        if isinstance(value, str):
            self.classified_ads_raw = value
        else:
            self.classified_ads_raw = json.dumps(value)

    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-edition_number']
        verbose_name = 'Gazette Edition'
        verbose_name_plural = 'Gazette Editions'

    def __str__(self):
        return f'The FPL Boys Gazette - Issue #{self.edition_number} (GW {self.gameweek.number})'


class ManagerRoastItem(models.Model):
    edition = models.ForeignKey(
        RoastEdition,
        on_delete=models.CASCADE,
        related_name='manager_roasts'
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='news_roasts'
    )
    rank_in_gw = models.IntegerField(default=1)
    net_points = models.IntegerField(default=0)
    badge = models.CharField(max_length=50, default='MID-TABLE')
    roast_title = models.CharField(max_length=255)
    roast_body = models.TextField()
    verdict = models.CharField(max_length=200, default='Verdict: Needs divine intervention')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['rank_in_gw', 'order']
        verbose_name = 'Manager Roast'
        verbose_name_plural = 'Manager Roasts'

    def __str__(self):
        return f'{self.member.manager_name} ({self.badge}) - GW {self.edition.gameweek.number}'
