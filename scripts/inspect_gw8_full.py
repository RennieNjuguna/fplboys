import os
import sys
import django
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from league.services.fpl_client import FPLSyncService
from league.models import Member, GameweekResult, Gameweek

def inspect_gw8():
    s = FPLSyncService()
    bootstrap = s.fetch_bootstrap()
    teams = {t['id']: t['name'] for t in bootstrap['teams']}
    team_shorts = {t['id']: t['short_name'] for t in bootstrap['teams']}
    players = {p['id']: p for p in bootstrap['elements']}

    # 1. Official Fixtures
    fixtures_resp = requests.get('https://fantasy.premierleague.com/api/fixtures/?event=8', headers={"User-Agent": "Mozilla/5.0"}).json()
    print("=================== OFFICIAL GW 8 FIXTURES & SCORES ===================")
    for f in fixtures_resp:
        h_name = teams.get(f['team_h'], f"Team {f['team_h']}")
        a_name = teams.get(f['team_a'], f"Team {f['team_a']}")
        h_score = f.get('team_h_score', 0)
        a_score = f.get('team_a_score', 0)
        print(f"  {h_name} {h_score} - {a_score} {a_name} (Finished: {f.get('finished')})")

    # 2. Live stats
    live_resp = s.fetch_event_live(8)
    live_stats = {el['id']: el for el in live_resp.get('elements', [])}

    print("\n=================== TOP PERFORMING PLAYERS IN GW 8 ===================")
    top_players = []
    for el_id, el_data in live_stats.items():
        p_info = players.get(el_id, {})
        pts = el_data.get('stats', {}).get('total_points', 0)
        stats = el_data.get('stats', {})
        goals = stats.get('goals_scored', 0)
        assists = stats.get('assists', 0)
        clean_sheets = stats.get('clean_sheets', 0)
        bonus = stats.get('bonus', 0)
        t_short = team_shorts.get(p_info.get('team'), '')
        p_name = p_info.get('web_name', f"Player {el_id}").encode('ascii', 'replace').decode('ascii')
        top_players.append((p_name, t_short, pts, goals, assists, clean_sheets, bonus))

    top_players.sort(key=lambda x: x[2], reverse=True)
    for p in top_players[:20]:
        print(f"  {p[0]} ({p[1]}): {p[2]} pts | Goals: {p[3]}, Assists: {p[4]}, CS: {p[5]}, Bonus: {p[6]}")

    print("\n=================== GW 8 SQUAD & MANAGER AUDIT ===================")
    gw8 = Gameweek.objects.get(number=8)
    res_list = list(GameweekResult.objects.filter(gameweek=gw8).select_related('member').order_by('league_rank', '-net_points'))
    
    # Flagged from screenshot: Chris, Marve, Erick, Dennis, Aron
    flagged = ['Chris', 'Marve', 'Erick', 'Dennis', 'Aron']

    manager_summaries = []

    for r in res_list:
        m = r.member
        picks = s.fetch_entry_picks(m.fpl_entry_id, 8)
        hist = picks.get('entry_history', {})
        pts = hist.get('points', r.gw_points)
        hits = hist.get('event_transfers_cost', r.transfer_cost)
        net = pts - hits
        chip = picks.get('active_chip') or "None"
        transfers = hist.get('event_transfers', 0)
        bench_pts = hist.get('points_on_bench', 0)

        cap_str = ""
        vice_str = ""
        starters = []
        bench = []

        for p in picks.get('picks', []):
            el_id = p['element']
            p_data = players.get(el_id, {})
            p_name = p_data.get('web_name', f"Player {el_id}").encode('ascii', 'replace').decode('ascii')
            t_short = team_shorts.get(p_data.get('team'), '')
            el_pts = live_stats.get(el_id, {}).get('stats', {}).get('total_points', 0)
            mult = p.get('multiplier', 1)
            tot = el_pts * mult

            if p.get('is_captain'):
                cap_str = f"{p_name} ({el_pts} x {mult} = {tot}p)"
            if p.get('is_vice_captain'):
                vice_str = f"{p_name} ({el_pts}p)"

            if mult > 0:
                starters.append((p_name, tot, el_pts, t_short))
            else:
                bench.append((p_name, el_pts, t_short))

        starters.sort(key=lambda x: x[1], reverse=True)
        bench.sort(key=lambda x: x[1], reverse=True)

        is_flagged = any(fn in m.manager_name for fn in flagged)
        flag_str = "[FLAGGED / INELIGIBLE]" if is_flagged else "[PAID / ELIGIBLE]"

        manager_summaries.append({
            'rank': r.league_rank,
            'name': m.manager_name,
            'team': m.team_name,
            'net': net,
            'gross': pts,
            'hits': hits,
            'chip': chip,
            'transfers': transfers,
            'cap': cap_str,
            'vice': vice_str,
            'bench_pts': bench_pts,
            'starters': starters,
            'bench': bench,
            'flagged': is_flagged
        })

    # Sort managers by net points descending, then gross points descending
    manager_summaries.sort(key=lambda x: (x['net'], x['gross']), reverse=True)

    for idx, ms in enumerate(manager_summaries, 1):
        flag_str = "[FLAGGED / INELIGIBLE]" if ms['flagged'] else "[PAID / ELIGIBLE]"
        print(f"GW Rank {idx} (Overall Rank {ms['rank']}): {ms['name']} ({ms['team']}) - Net: {ms['net']} (Gross: {ms['gross']}, Hit: -{ms['hits']}) {flag_str}")
        print(f"   Chip: {ms['chip']} | Transfers: {ms['transfers']} | Captain: {ms['cap']} | Vice: {ms['vice']}")
        print(f"   Bench Points Wasted: {ms['bench_pts']} pts -> {', '.join([f'{b[0]} ({b[1]}p)' for b in ms['bench']])}")
        print(f"   Top Starters: {', '.join([f'{s[0]} ({s[1]}p)' for s in ms['starters'][:5]])}")
        print(f"   Lowest Starters: {', '.join([f'{s[0]} ({s[1]}p)' for s in ms['starters'][-3:]])}")
        print("-" * 80)

if __name__ == '__main__':
    inspect_gw8()
