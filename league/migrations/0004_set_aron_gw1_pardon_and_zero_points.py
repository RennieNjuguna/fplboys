from decimal import Decimal
from django.db import migrations


def set_aron_gw1_pardon(apps, schema_editor):
    Member = apps.get_model('league', 'Member')
    Gameweek = apps.get_model('league', 'Gameweek')
    GameweekResult = apps.get_model('league', 'GameweekResult')
    Payment = apps.get_model('treasury', 'Payment')

    # 1. Update Aron's joined_gameweek to 2
    aron = Member.objects.filter(manager_name__icontains='Aron').first()
    if not aron:
        aron = Member.objects.filter(fpl_entry_id=9266887).first()

    if aron:
        aron.joined_gameweek = 2
        aron.save(update_fields=['joined_gameweek'])

        # 2. Update Aron's GW1 result to 0 points
        gw1 = Gameweek.objects.filter(number=1).first()
        if gw1:
            gw1_res = GameweekResult.objects.filter(member=aron, gameweek=gw1).first()
            if gw1_res:
                gw1_res.gw_points = 0
                gw1_res.transfer_cost = 0
                gw1_res.net_points = 0
                gw1_res.overall_rank = 0
                gw1_res.gw_prize_won = Decimal('0.00')
                gw1_res.is_top3 = False
                gw1_res.save(update_fields=['gw_points', 'transfer_cost', 'net_points', 'overall_rank', 'gw_prize_won', 'is_top3'])

            # 3. Ensure no payment/unpaid record for GW1
            Payment.objects.filter(member=aron, gameweek=gw1).delete()

            # 4. Re-rank GW1 results
            results = list(GameweekResult.objects.filter(gameweek=gw1).order_by('-net_points', '-gw_points'))
            for idx, res in enumerate(results, start=1):
                res.league_rank = idx
                res.save(update_fields=['league_rank'])


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('league', '0003_member_joined_gameweek'),
        ('treasury', '0003_auto_20260828_2037'),
    ]

    operations = [
        migrations.RunPython(set_aron_gw1_pardon, reverse_func),
    ]
