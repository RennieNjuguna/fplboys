from decimal import Decimal
from django.db import models
from django.utils import timezone
import pytz


class Member(models.Model):
    """
    Represents an FPL manager in the 10-member mini-league.
    """
    fpl_entry_id = models.IntegerField(unique=True, help_text="FPL team entry ID")
    team_name = models.CharField(max_length=120)
    manager_name = models.CharField(max_length=120)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Phone number for M-Pesa / reminders (e.g., 254712345678)"
    )
    avatar_url = models.CharField(max_length=400, blank=True, null=True)
    joined_gameweek = models.IntegerField(default=1, help_text="Gameweek number when the member joined the league")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['manager_name']
        verbose_name = "Member"
        verbose_name_plural = "Members"

    def __str__(self):
        return f"{self.manager_name} ({self.team_name})"

    @property
    def total_overall_points(self):
        # Sum of net points across finished and active gameweeks
        total = self.gw_results.filter(gameweek__status__in=['finished', 'active']).aggregate(
            models.Sum('net_points')
        )['net_points__sum']
        return total or 0

    @property
    def total_prizes_won(self):
        # Sum of GW prizes won
        total = self.gw_results.aggregate(
            models.Sum('gw_prize_won')
        )['gw_prize_won__sum']
        return Decimal(str(total or 0.00))

    @property
    def total_paid_contributions(self):
        # Sum of verified payments
        from treasury.models import Payment
        total = Payment.objects.filter(
            member=self, verified=True
        ).aggregate(models.Sum('amount_paid'))['amount_paid__sum']
        return Decimal(str(total or 0.00))

    @property
    def total_fines_incurred(self):
        from treasury.models import Payment
        total = Payment.objects.filter(
            member=self, verified=True, is_late=True
        ).aggregate(models.Sum('late_fine_amount'))['late_fine_amount__sum']
        return Decimal(str(total or 0.00))

    @property
    def net_profit_loss(self):
        """
        Net Profit/Loss = Total Prizes Won - (Total Standard Contributions Paid + Total Fines Paid)
        """
        return self.total_prizes_won - self.total_paid_contributions


class Gameweek(models.Model):
    """
    Represents an FPL Gameweek (1 to 38).
    """
    STATUS_CHOICES = (
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('finished', 'Finished'),
    )

    number = models.IntegerField(unique=True)
    name = models.CharField(max_length=60)
    deadline_time = models.DateTimeField(help_text="Official FPL Gameweek deadline (UTC)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    is_current = models.BooleanField(default=False)
    is_next = models.BooleanField(default=False)
    month = models.IntegerField(default=8, help_text="Month number 1-12 for monthly filters")
    season = models.CharField(max_length=20, default="2026/27")
    payout_calculated = models.BooleanField(default=False)
    prize_pool_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('500.00'))

    class Meta:
        ordering = ['number']
        verbose_name = "Gameweek"
        verbose_name_plural = "Gameweeks"

    def __str__(self):
        return f"GW {self.number} ({self.status.capitalize()})"

    @property
    def deadline_eat(self):
        """Convert deadline time to East Africa Time (UTC+3)"""
        if not self.deadline_time:
            return None
        eat_tz = pytz.timezone('Africa/Nairobi')
        return self.deadline_time.astimezone(eat_tz)

    @property
    def start_time(self):
        """
        Official Gameweek Start / Kickoff time (when the first match of that GW starts).
        In Premier League / FPL, kickoff is standard 90 minutes after the transfer deadline closes.
        """
        if not self.deadline_time:
            return None
        return self.deadline_time + timezone.timedelta(minutes=90)

    @property
    def start_time_eat(self):
        """Gameweek start / kickoff in East Africa Time (UTC+3)"""
        st = self.start_time
        if not st:
            return None
        eat_tz = pytz.timezone('Africa/Nairobi')
        return st.astimezone(eat_tz)

    @property
    def is_past_deadline(self):
        """True if FPL transfers have closed (90m before kickoff)"""
        if not self.deadline_time:
            return False
        return timezone.now() > self.deadline_time

    @property
    def is_past_start(self):
        """True if the first match of the Gameweek has started / kicked off"""
        st = self.start_time
        if not st:
            return False
        return timezone.now() >= st


class GameweekResult(models.Model):
    """
    Stores FPL performance and financial winnings for a member in a specific gameweek.
    """
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='gw_results')
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name='results')
    gw_points = models.IntegerField(default=0, help_text="Gross GW points before hits")
    transfer_cost = models.IntegerField(default=0, help_text="Transfer cost points deduction")
    net_points = models.IntegerField(default=0, help_text="Net GW points = gw_points - transfer_cost")
    overall_rank = models.IntegerField(default=0, help_text="FPL Global Overall Rank")
    league_rank = models.IntegerField(default=0, help_text="Rank within FPL Boys mini-league for this GW")
    last_rank = models.IntegerField(default=0, help_text="Rank in previous gameweek for tracker arrow")
    gw_prize_won = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Prize won for top 3 finish in this GW"
    )
    is_top3 = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('member', 'gameweek')
        ordering = ['gameweek', 'league_rank', '-net_points']
        verbose_name = "Gameweek Result"
        verbose_name_plural = "Gameweek Results"

    def __str__(self):
        return f"{self.member.manager_name} - GW {self.gameweek.number}: {self.net_points} pts (Won: Ksh. {self.gw_prize_won})"

    def save(self, *args, **kwargs):
        self.net_points = self.gw_points - self.transfer_cost
        super().save(*args, **kwargs)

    @property
    def rank_movement(self):
        """
        Calculates rank tracker movement vs last_rank:
        Returns dict with direction ('up', 'down', 'same'), diff, symbol, and css color class.
        """
        if not self.last_rank or self.last_rank == 0:
            return {'direction': 'same', 'diff': 0, 'symbol': '—', 'color': 'text-gray-500'}

        diff = self.last_rank - self.league_rank
        if diff > 0:
            return {'direction': 'up', 'diff': diff, 'symbol': '▲', 'color': 'text-emerald-400 font-bold'}
        elif diff < 0:
            return {'direction': 'down', 'diff': abs(diff), 'symbol': '▼', 'color': 'text-rose-500 font-bold'}
        else:
            return {'direction': 'same', 'diff': 0, 'symbol': '—', 'color': 'text-gray-400'}
