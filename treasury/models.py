from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from league.models import Member, Gameweek


class TreasuryConfig(models.Model):
    """
    Singleton configuration for Treasury access and admin security settings.
    Stores the hashed treasury admin password in the database.
    """
    admin_password_hash = models.CharField(max_length=255, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Treasury Configuration"
        verbose_name_plural = "Treasury Configuration"

    def __str__(self):
        return "Treasury Admin Security Config"

    @classmethod
    def get_config(cls):
        config = cls.objects.first()
        if not config:
            config = cls.objects.create(admin_password_hash=make_password("@FPLBoyz254??"))
        return config

    def set_admin_password(self, raw_password):
        self.admin_password_hash = make_password(raw_password)
        self.save()

    def check_admin_password(self, raw_password):
        if not self.admin_password_hash:
            # Default fallback if empty
            return raw_password == "@FPLBoyz254??"
        return django_check_password(raw_password, self.admin_password_hash)


WAIVED_FINE_GAMEWEEKS = (1, 2, 19, 38)


class Payment(models.Model):
    """
    Represents a weekly contribution payment made by a member for a gameweek.
    Standard amount: Ksh. 150.
    Late fine: Ksh. 50 (if timestamp_received > gameweek.deadline_time).
    Waiver: GW1, GW2, GW19, and GW38 have no late fines.
    """
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='payments')
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('150.00'),
        help_text="Amount paid in Ksh."
    )
    timestamp_received = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp when M-Pesa payment was received"
    )
    mpesa_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="M-Pesa transaction reference (e.g. QJH78291KL)"
    )
    verified = models.BooleanField(
        default=True,
        help_text="Whether this payment has been verified by the treasurer"
    )
    is_late = models.BooleanField(
        default=False,
        help_text="Automatically set to True if received after the official GW deadline (except waived GWs)"
    )
    late_fine_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Late fine assessed (routed into BBQ Pot, typically Ksh. 50)"
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('member', 'gameweek')
        ordering = ['-timestamp_received', '-gameweek__number']
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        late_tag = " [LATE]" if self.is_late else ""
        return f"{self.member.manager_name} - GW {self.gameweek.number} - Ksh. {self.amount_paid}{late_tag}"

    def check_is_late(self):
        """Check if received strictly after gameweek deadline (except waived GWs)"""
        if self.gameweek and self.gameweek.number in WAIVED_FINE_GAMEWEEKS:
            return False
        if self.gameweek and self.gameweek.deadline_time and self.timestamp_received:
            return self.timestamp_received > self.gameweek.deadline_time
        return False

    def save(self, *args, **kwargs):
        # Auto-compute late status (waiver for GW1, GW2, GW19, GW38)
        if self.gameweek and self.gameweek.number in WAIVED_FINE_GAMEWEEKS:
            self.is_late = False
            self.late_fine_amount = Decimal('0.00')
        else:
            calculated_late = self.check_is_late()
            self.is_late = calculated_late
            if self.is_late:
                if not self.late_fine_amount or self.late_fine_amount == Decimal('0.00'):
                    self.late_fine_amount = Decimal('50.00')
            else:
                self.late_fine_amount = Decimal('0.00')

        super().save(*args, **kwargs)



class PrizePayout(models.Model):
    """
    Tracks cash payouts and prize distributions disbursed to managers.
    Ensures disbursed prize money is deducted from available rollover balances.
    """
    PAYOUT_METHOD_CHOICES = (
        ('MPESA_CASH', 'M-Pesa Cash Disbursal'),
        ('REINVESTED', 'Reinvested in Future GWs'),
    )
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='prize_payouts')
    gameweek = models.ForeignKey(Gameweek, on_delete=models.SET_NULL, null=True, blank=True, related_name='prize_payouts')
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount disbursed in Ksh.")
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHOD_CHOICES, default='MPESA_CASH')
    mpesa_reference = models.CharField(max_length=50, blank=True, null=True, help_text="Outgoing M-Pesa Transaction Ref (e.g. QLK983021LK)")
    notes = models.TextField(blank=True, default="")
    disbursed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-disbursed_at']
        verbose_name = "Prize Payout"
        verbose_name_plural = "Prize Payouts"

    def __str__(self):
        return f"{self.member.manager_name} - Ksh. {self.amount} ({self.payout_method})"


class AuditLog(models.Model):
    """
    Log of treasury activities, syncs, reminders, and payment updates.
    """
    ACTION_CHOICES = (
        ('PAYMENT_CREATED', 'Payment Created'),
        ('PAYMENT_UPDATED', 'Payment Updated'),
        ('PAYMENT_DELETED', 'Payment Deleted'),
        ('PRIZE_DISBURSED', 'Prize Disbursed via M-Pesa'),
        ('REMINDER_GENERATED', 'Reminder Generated'),
        ('FPL_SYNC', 'FPL Sync Performed'),
        ('PAYOUT_CALCULATED', 'Payout Calculated'),
        ('TREASURY_UNLOCKED', 'Treasury Unlocked with Admin Password'),
    )

    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField()
    performed_by = models.CharField(max_length=100, default='System / Treasurer')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.action}: {self.description[:50]}"

