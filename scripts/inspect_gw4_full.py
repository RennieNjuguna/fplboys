import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from league.models import Member
from league.services.fpl_client import FPLSyncService

def check_gw4_full():
    s = FPLSyncService()
    bootstrap = s.fetch_bootstrap()
    players = {p['id']: p for p in bootstrap['elements']}
    teams = {t['id']: t['short_name'] for t in bootstrap['teams']}
    live = s.fetch_event_live(4)
    live_pts = {el['id']: el.get('stats', {}).get('total_points', 0) for el in live.get('elements', [])}

    members = list(Member.objects.all())

    all_data = []

    for m in members:
        picks = s.fetch_entry_picks(m.fpl_entry_id, 4)
        if not picks:
            continue
        hist = picks.get('entry_history', {})
        starters = []
        bench = []
        cap_str = ""
        vice_str = ""
        for p in picks.get('picks', []):
            el_id = p['element']
            p_data = players.get(el_id, {})
            p_name = p_data.get('web_name', f"Player {el_id}")
            t_name = teams.get(p_data.get('team'), '')
            pts = live_pts.get(el_id, 0)
            mult = p.get('multiplier', 1)
            total = pts * mult

            info_str = f"{p_name} ({t_name}): {total}pts"

            if p.get('is_captain'):
                cap_str = f"{p_name} ({pts} x {mult} = {total} pts)"
            if p.get('is_vice_captain'):
                vice_str = f"{p_name} ({pts} pts)"

            if mult > 0:
                starters.append((p_name, total, pts))
            else:
                bench.append((p_name, pts))

        all_data.append({
            'member': m,
            'points': hist.get('points', 0),
            'transfers': hist.get('event_transfers', 0),
            'transfer_cost': hist.get('event_transfers_cost', 0),
            'bench_points': hist.get('points_on_bench', 0),
            'chip': picks.get('active_chip'),
            'captain': cap_str,
            'vice_captain': vice_str,
            'starters': starters,
            'bench': bench,
        })

    all_data.sort(key=lambda x: x['points'], reverse=True)

    print("====================== GAMEWEEK 4 DETAILED AUDIT ======================\n")
    for idx, d in enumerate(all_data, 1):
        m = d['member']
        chip_str = f" [CHIP: {d['chip'].upper()}]" if d['chip'] else ""
        print(f"#{idx} {m.manager_name} ({m.team_name}) - Net Points: {d['points']}{chip_str}")
        print(f"   Transfers Made: {d['transfers']} | Cost / Hit: -{d['transfer_cost']} pts")
        print(f"   Captain: {d['captain']} | Vice-Captain: {d['vice_captain']}")
        print(f"   Bench Points: {d['bench_points']} pts -> Bench: {', '.join([f'{b[0]} ({b[1]}p)' for b in d['bench']])}")
        # Top 3 scorers
        sorted_starters = sorted(d['starters'], key=lambda x: x[1], reverse=True)
        top_str = ', '.join([f"{s[0]} ({s[1]}p)" for s in sorted_starters[:4]])
        print(f"   Top Starters: {top_str}")
        print("-" * 75)

if __name__ == '__main__':
    check_gw4_full()
