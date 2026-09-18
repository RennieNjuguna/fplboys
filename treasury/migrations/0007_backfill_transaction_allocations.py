from decimal import Decimal
from django.db import migrations


def backfill_transaction_allocations(apps, schema_editor):
    Payment = apps.get_model('treasury', 'Payment')
    PaymentTransaction = apps.get_model('treasury', 'PaymentTransaction')
    TransactionAllocation = apps.get_model('treasury', 'TransactionAllocation')
    PrizePayout = apps.get_model('treasury', 'PrizePayout')

    for payment in Payment.objects.all():
        if not payment.transaction:
            is_prize = bool(payment.mpesa_code and 'PRIZE' in payment.mpesa_code.upper())
            tx_type = 'PRIZE_ROLLOVER' if is_prize else 'MPESA'
            tx = PaymentTransaction.objects.create(
                member=payment.member,
                amount=payment.amount_paid,
                starting_gameweek=payment.gameweek,
                mpesa_code=payment.mpesa_code or ('PRIZE-WINNINGS' if is_prize else None),
                timestamp_received=payment.timestamp_received,
                transaction_type=tx_type,
                notes=f'Auto-backfilled parent transaction for GW {payment.gameweek.number}',
                verified=payment.verified
            )
            payment.transaction = tx
            payment.save(update_fields=['transaction'])
        else:
            tx = payment.transaction

        if not TransactionAllocation.objects.filter(transaction=tx, payment=payment).exists():
            TransactionAllocation.objects.create(
                transaction=tx,
                payment=payment,
                amount=payment.amount_paid
            )

    for payout in PrizePayout.objects.filter(payout_method='REINVESTED', transaction__isnull=True):
        matching_tx = PaymentTransaction.objects.filter(
            member=payout.member,
            transaction_type='PRIZE_ROLLOVER',
            starting_gameweek=payout.gameweek
        ).first()
        if matching_tx:
            payout.transaction = matching_tx
            payout.save(update_fields=['transaction'])


def reverse_backfill(apps, schema_editor):
    TransactionAllocation = apps.get_model('treasury', 'TransactionAllocation')
    TransactionAllocation.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('treasury', '0006_auto_20260918_1235'),
    ]

    operations = [
        migrations.RunPython(backfill_transaction_allocations, reverse_backfill),
    ]
