import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from news.services.gw_analyzer import analyze_gameweek_performance
from treasury.models import Payment
from league.models import Gameweek

def run(gw_num=3):
    data = analyze_gameweek_performance(gw_num)
    gw = Gameweek.objects.get(number=gw_num)
    payments = {p.member_id: p for p in Payment.objects.filter(gameweek=gw, verified=True)}

    print(f"\n================ GAMEWEEK {gw_num} COMPREHENSIVE OVERVIEW ================\n")
    for m in data['managers']:
        p = payments.get(m['member_id'])
        payment_status = "PAID ON TIME" if (p and not p.is_late) else ("PAID LATE" if (p and p.is_late) else "UNPAID")
        cap = m['captain']['name'] if m['captain'] else "None"
        cap_pts = m['captain']['total_points'] if m['captain'] else 0
        top_s = ", ".join([f"{x['name']} ({x['points']}p)" for x in m['top_scorers']])
        chip = m['active_chip'] or "None"
        print(f"Rank {m['rank_in_gw']}: {m['manager_name']} ({m['team_name']})")
        print(f"   Net Points: {m['net_points']} (Gross: {m['gw_points']}, Hit: -{m['transfer_cost']})")
        print(f"   Chip: {chip} | Captain: {cap} ({cap_pts} pts, mult={m['captain']['multiplier'] if m['captain'] else 1})")
        print(f"   Bench Points Wasted: {m['bench_points']} pts")
        print(f"   Top Starters: {top_s}")
        print(f"   Financials: Prize Won = Ksh {m['prize_won']:,.2f} | Status: {payment_status}")
        print("-" * 60)

if __name__ == '__main__':
    run(3)
