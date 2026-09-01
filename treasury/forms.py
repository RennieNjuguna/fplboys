from decimal import Decimal
from django import forms
from django.utils import timezone
from league.models import Member, Gameweek
from treasury.models import Payment


class LogMpesaPaymentForm(forms.Form):
    """
    Fast entry form for the Treasurer Portal to log incoming M-Pesa payments.
    Automatically assigns payments in sequential FIFO order starting from
    the member's earliest unpaid or partially paid gameweek.
    """
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(is_active=True).order_by('manager_name'),
        widget=forms.Select(attrs={
            'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-semibold rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5',
            'id': 'id_member'
        })
    )
    amount_paid = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=Decimal('150.00'),
        widget=forms.NumberInput(attrs={
            'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-mono font-bold rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5',
            'step': '0.01',
            'id': 'id_amount_paid'
        })
    )
    timestamp_received = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-mono rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5',
            'type': 'datetime-local',
            'id': 'id_timestamp_received'
        })
    )
    mpesa_code = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-mono font-bold rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5 uppercase',
            'placeholder': 'e.g. QJH89302LM'
        })
    )
    verified = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-emerald-600 bg-gray-800 border-gray-700 rounded focus:ring-emerald-500'
        })
    )
    notes = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5',
            'placeholder': 'Optional notes'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'timestamp_received' not in self.initial:
            self.initial['timestamp_received'] = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            'member',
            'gameweek',
            'amount_paid',
            'timestamp_received',
            'mpesa_code',
            'verified',
            'notes',
        ]
        widgets = {
            'member': forms.Select(attrs={
                'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-semibold rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5'
            }),
            'gameweek': forms.Select(attrs={
                'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-semibold rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5',
                'id': 'id_gameweek'
            }),
            'amount_paid': forms.NumberInput(attrs={
                'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-mono font-bold rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5',
                'step': '0.01',
                'id': 'id_amount_paid'
            }),
            'timestamp_received': forms.DateTimeInput(attrs={
                'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-mono rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5',
                'type': 'datetime-local',
                'id': 'id_timestamp_received'
            }),
            'mpesa_code': forms.TextInput(attrs={
                'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm font-mono font-bold rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5 uppercase',
                'placeholder': 'e.g. QJH89302LM'
            }),
            'verified': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-emerald-600 bg-gray-800 border-gray-700 rounded focus:ring-emerald-500'
            }),
            'notes': forms.TextInput(attrs={
                'class': 'bg-gray-800 border border-purple-700/60 text-white text-base sm:text-sm rounded-xl focus:ring-fpl-green focus:border-fpl-green block w-full p-2.5 sm:p-2.5',
                'placeholder': 'Optional notes'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'timestamp_received' not in self.initial:
            self.initial['timestamp_received'] = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
        elif self.instance.pk and self.instance.timestamp_received:
            self.initial['timestamp_received'] = timezone.localtime(self.instance.timestamp_received).strftime('%Y-%m-%dT%H:%M')
        if not self.instance.pk and 'amount_paid' not in self.initial:
            self.initial['amount_paid'] = Decimal('150.00')

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def validate_unique(self):
        # Allow view to handle existing payments gracefully via top-up or carryover
        pass

