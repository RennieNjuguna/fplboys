from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum, Max, Min, Avg
from league.models import Member, Gameweek, GameweekResult
from treasury.models import Payment
from treasury.services.pot_calculator import get_treasury_summary, get_member_financial_leaderboard


def get_rank_movement_dict(current_rank, prev_rank):
    if not prev_rank or prev_rank == 0:
        return {'direction': 'same', 'diff': 0, 'symbol': '—', 'color': 'text-gray-500'}
    diff = prev_rank - current_rank
    if diff > 0:
        return {'direction': 'up', 'diff': diff, 'symbol': '▲', 'color': 'text-emerald-400 font-black'}
    elif diff < 0:
        return {'direction': 'down', 'diff': abs(diff), 'symbol': '▼', 'color': 'text-rose-500 font-black'}
    else:
        return {'direction': 'same', 'diff': 0, 'symbol': '—', 'color': 'text-gray-400'}


def dashboard_overview(request):
    """
    Main home dashboard: Sleek leaderboards, live pots summary, and latest podium winners.
    Automatically advances to the latest gameweek with results, with selector for past GW podiums.
    """
    treasury = get_treasury_summary()
    leaderboard_financial = get_member_financial_leaderboard()

    # All gameweeks with results (or finished)
    available_gws = list(Gameweek.objects.filter(results__isnull=False).distinct().order_by('number'))
    if not available_gws:
        available_gws = list(Gameweek.objects.filter(status='finished').order_by('number'))
    latest_gw = available_gws[-1] if available_gws else None

    # Selected GW for podium (defaults to latest GW with results)
    selected_podium_gw_num = request.GET.get('podium_gw')
    selected_podium_gw = latest_gw
    if selected_podium_gw_num:
        try:
            selected_podium_gw = Gameweek.objects.get(number=int(selected_podium_gw_num))
        except (Gameweek.DoesNotExist, ValueError):
            selected_podium_gw = latest_gw

    gw_podium = []
    if selected_podium_gw:
        gw_podium = selected_podium_gw.results.filter(is_top3=True).select_related('member').order_by('league_rank')

    # Next upcoming/active gameweek
    current_or_next_gw = Gameweek.objects.filter(status__in=['active', 'upcoming']).order_by('number').first()

    # Overall Standings with Rank Tracker Arrows
    members = list(Member.objects.filter(is_active=True))

    # Calculate previous GW cumulative totals to determine previous overall ranks
    prev_totals = {}
    if len(available_gws) >= 2:
        prev_gws = available_gws[:-1]
        for m in members:
            pts = GameweekResult.objects.filter(member=m, gameweek__in=prev_gws).aggregate(
                Sum('net_points')
            )['net_points__sum'] or 0
            prev_totals[m.id] = pts
        # Sort prev totals to assign prev ranks
        sorted_prev = sorted(members, key=lambda x: prev_totals.get(x.id, 0), reverse=True)
        prev_rank_map = {m.id: idx for idx, m in enumerate(sorted_prev, start=1)}
    else:
        prev_rank_map = {}

    standings_summary = []
    for m in members:
        latest_res = GameweekResult.objects.filter(member=m, gameweek=latest_gw).first() if latest_gw else None
        latest_gw_net = latest_res.net_points if latest_res else 0
        latest_gw_hits = latest_res.transfer_cost if latest_res else 0

        standings_summary.append({
            'member': m,
            'total_points': m.total_overall_points,
            'latest_gw_net': latest_gw_net,
            'latest_gw_hits': latest_gw_hits,
            'total_won': m.total_prizes_won,
            'net_pl': m.net_profit_loss,
            'prev_rank': prev_rank_map.get(m.id, 0),
        })

    standings_summary.sort(key=lambda x: x['total_points'], reverse=True)
    for idx, item in enumerate(standings_summary, start=1):
        item['rank'] = idx
        item['movement'] = get_rank_movement_dict(idx, item['prev_rank'])

    context = {
        'treasury': treasury,
        'latest_finished_gw': latest_gw,
        'selected_podium_gw': selected_podium_gw,
        'finished_gws': available_gws,
        'gw_podium': gw_podium,
        'current_or_next_gw': current_or_next_gw,
        'standings_summary': standings_summary,
        'financial_leaderboard': leaderboard_financial[:5],
    }
    return render(request, 'dashboard/index.html', context)



def standings_view(request):
    """
    Standings Hub with filters:
    - Overall Total Points
    - Specific Gameweek
    - Monthly Rankings
    """
    filter_type = request.GET.get('type', 'overall')  # 'overall', 'gw', 'month'
    selected_gw_num = request.GET.get('gw')
    selected_month = request.GET.get('month')

    all_gws = Gameweek.objects.all().order_by('number')
    finished_gws = Gameweek.objects.filter(status__in=['finished', 'active']).order_by('number')

    # Available months with names
    month_names = {
        8: 'August 2026', 9: 'September 2026', 10: 'October 2026',
        11: 'November 2026', 12: 'December 2026', 1: 'January 2027',
        2: 'February 2027', 3: 'March 2027', 4: 'April 2027', 5: 'May 2027'
    }
    available_months = Gameweek.objects.values_list('month', flat=True).distinct()
    months_list = [{'num': m, 'name': month_names.get(m, f"Month {m}")} for m in available_months]

    members = list(Member.objects.filter(is_active=True))
    standings_rows = []

    if filter_type == 'gw' and selected_gw_num:
        try:
            target_gw = Gameweek.objects.get(number=int(selected_gw_num))
            results = target_gw.results.select_related('member').order_by('league_rank', '-net_points')
            for r in results:
                standings_rows.append({
                    'rank': r.league_rank,
                    'member': r.member,
                    'gw_points': r.gw_points,
                    'transfer_cost': r.transfer_cost,
                    'net_points': r.net_points,
                    'overall_rank': r.overall_rank,
                    'prize_won': r.gw_prize_won,
                    'is_top3': r.is_top3,
                    'movement': r.rank_movement,
                })
        except Gameweek.DoesNotExist:
            filter_type = 'overall'

    elif filter_type == 'month' and selected_month:
        month_int = int(selected_month)
        month_gws = Gameweek.objects.filter(month=month_int, status__in=['finished', 'active'])
        for m in members:
            res_agg = GameweekResult.objects.filter(member=m, gameweek__in=month_gws).aggregate(
                total_pts=Sum('net_points'),
                total_gross=Sum('gw_points'),
                total_hits=Sum('transfer_cost'),
                total_won=Sum('gw_prize_won')
            )
            standings_rows.append({
                'member': m,
                'gw_points': res_agg['total_gross'] or 0,
                'transfer_cost': res_agg['total_hits'] or 0,
                'net_points': res_agg['total_pts'] or 0,
                'prize_won': res_agg['total_won'] or Decimal('0.00'),
            })
        standings_rows.sort(key=lambda x: x['net_points'], reverse=True)
        for idx, row in enumerate(standings_rows, start=1):
            row['rank'] = idx
            row['movement'] = {'direction': 'same', 'diff': 0, 'symbol': '—', 'color': 'text-gray-500'}

    else:
        # Default: Overall Standings with previous GW comparison
        filter_type = 'overall'
        all_finished = list(Gameweek.objects.filter(status='finished').order_by('number'))
        prev_totals = {}
        if len(all_finished) >= 2:
            prev_gws = all_finished[:-1]
            for m in members:
                pts = GameweekResult.objects.filter(member=m, gameweek__in=prev_gws).aggregate(
                    Sum('net_points')
                )['net_points__sum'] or 0
                prev_totals[m.id] = pts
            sorted_prev = sorted(members, key=lambda x: prev_totals.get(x.id, 0), reverse=True)
            prev_rank_map = {m.id: idx for idx, m in enumerate(sorted_prev, start=1)}
        else:
            prev_rank_map = {}

        for m in members:
            res_agg = GameweekResult.objects.filter(member=m, gameweek__status__in=['finished', 'active']).aggregate(
                total_pts=Sum('net_points'),
                total_gross=Sum('gw_points'),
                total_hits=Sum('transfer_cost'),
                total_won=Sum('gw_prize_won')
            )
            latest_res = GameweekResult.objects.filter(member=m).order_by('-gameweek__number').first()
            overall_fpl_rank = latest_res.overall_rank if latest_res else 0

            standings_rows.append({
                'member': m,
                'gw_points': res_agg['total_gross'] or 0,
                'transfer_cost': res_agg['total_hits'] or 0,
                'net_points': res_agg['total_pts'] or 0,
                'prize_won': res_agg['total_won'] or Decimal('0.00'),
                'overall_rank': overall_fpl_rank,
                'prev_rank': prev_rank_map.get(m.id, 0),
            })
        standings_rows.sort(key=lambda x: x['net_points'], reverse=True)
        for idx, row in enumerate(standings_rows, start=1):
            row['rank'] = idx
            row['movement'] = get_rank_movement_dict(idx, row['prev_rank'])

    context = {
        'filter_type': filter_type,
        'selected_gw_num': int(selected_gw_num) if selected_gw_num else (finished_gws.first().number if finished_gws.exists() else 1),
        'selected_month': int(selected_month) if selected_month else 8,
        'all_gws': all_gws,
        'finished_gws': finished_gws,
        'months_list': months_list,
        'standings_rows': standings_rows,
    }
    return render(request, 'dashboard/standings.html', context)


def analytics_view(request):
    """
    Performance and financial analytics page with interactive Chart.js charts and Net P/L leaderboard.
    """
    leaderboard = get_member_financial_leaderboard()
    treasury = get_treasury_summary()

    context = {
        'leaderboard': leaderboard,
        'treasury': treasury,
    }
    return render(request, 'dashboard/analytics.html', context)


import json


def manager_detail_view(request, member_id):
    """
    Individual Manager performance profile, personal interactive graph, and financial statement.
    """
    member = get_object_or_404(Member, pk=member_id)
    gw_results = member.gw_results.select_related('gameweek').order_by('gameweek__number')
    payments = member.payments.select_related('gameweek').order_by('gameweek__number')
    transactions = member.transactions.select_related('starting_gameweek').prefetch_related('allocations', 'allocations__gameweek').order_by('-timestamp_received')

    # Aggregates
    total_points = member.total_overall_points
    total_won = member.total_prizes_won
    total_paid = member.total_paid_contributions
    total_fines = member.total_fines_incurred
    net_pl = member.net_profit_loss

    # Gameweek performance data for Chart.js
    gws_with_results = list(Gameweek.objects.filter(results__isnull=False).distinct().order_by('number'))
    if not gws_with_results:
        gws_with_results = list(Gameweek.objects.filter(status__in=['finished', 'active']).order_by('number'))

    gw_labels = []
    manager_net_points = []
    manager_gross_points = []
    manager_transfer_cost = []
    league_averages = []
    league_maximums = []
    manager_ranks = []
    cumulative_points = []
    cumulative_averages = []

    running_cum_points = 0
    running_cum_avg = 0.0
    times_beat_avg = 0
    best_gw_score = 0
    best_gw_name = "N/A"
    top3_finishes = 0

    for gw in gws_with_results:
        gw_labels.append(f"GW {gw.number}")
        
        # Manager result for this GW
        res = GameweekResult.objects.filter(member=member, gameweek=gw).first()
        net_pts = res.net_points if res else 0
        gross_pts = res.gw_points if res else 0
        hits = res.transfer_cost if res else 0
        rank = res.league_rank if res else 0

        manager_net_points.append(net_pts)
        manager_gross_points.append(gross_pts)
        manager_transfer_cost.append(hits)
        manager_ranks.append(rank if rank > 0 else None)

        running_cum_points += net_pts
        cumulative_points.append(running_cum_points)

        if rank in [1, 2, 3] or (res and res.is_top3):
            top3_finishes += 1

        if net_pts > best_gw_score:
            best_gw_score = net_pts
            best_gw_name = f"GW {gw.number}"

        # League aggregates for this GW
        league_stats = GameweekResult.objects.filter(gameweek=gw).aggregate(
            avg_pts=Avg('net_points'),
            max_pts=Max('net_points')
        )
        avg_pts = round(float(league_stats['avg_pts'] or 0), 1)
        max_pts = league_stats['max_pts'] or 0

        league_averages.append(avg_pts)
        league_maximums.append(max_pts)

        running_cum_avg += avg_pts
        cumulative_averages.append(round(running_cum_avg, 1))

        if net_pts > avg_pts:
            times_beat_avg += 1

    total_gws = len(gws_with_results)
    avg_score = round(total_points / total_gws, 1) if total_gws > 0 else 0.0
    beat_avg_pct = round((times_beat_avg / total_gws) * 100) if total_gws > 0 else 0

    chart_payload = {
        'gw_labels': gw_labels,
        'manager_net_points': manager_net_points,
        'manager_gross_points': manager_gross_points,
        'manager_transfer_cost': manager_transfer_cost,
        'league_averages': league_averages,
        'league_maximums': league_maximums,
        'manager_ranks': manager_ranks,
        'cumulative_points': cumulative_points,
        'cumulative_averages': cumulative_averages,
        'manager_name': member.manager_name,
    }

    graph_stats = {
        'best_gw_score': best_gw_score,
        'best_gw_name': best_gw_name,
        'avg_score': avg_score,
        'times_beat_avg': times_beat_avg,
        'beat_avg_pct': beat_avg_pct,
        'top3_finishes': top3_finishes,
        'total_gws': total_gws,
    }

    context = {
        'member': member,
        'gw_results': gw_results,
        'payments': payments,
        'transactions': transactions,
        'total_points': total_points,
        'total_won': total_won,
        'total_paid': total_paid,
        'total_fines': total_fines,
        'net_pl': net_pl,
        'chart_payload_json': json.dumps(chart_payload),
        'graph_stats': graph_stats,
    }
    return render(request, 'dashboard/manager_profile.html', context)


def api_charts_data(request):
    """
    JSON API providing datasets for Chart.js interactive charts.
    """
    members = list(Member.objects.filter(is_active=True).order_by('manager_name'))
    gws = list(Gameweek.objects.filter(status__in=['finished', 'active']).order_by('number'))
    if not gws:
        gws = list(Gameweek.objects.filter(number=1))

    gw_labels = [f"GW {gw.number}" for gw in gws]

    # 1. Cumulative Points Race
    color_palette = [
        '#00ff87', '#02efff', '#e90052', '#38003c', '#ff2882',
        '#04f5ff', '#ffb703', '#9d4edd', '#06d6a0', '#118ab2'
    ]

    points_datasets = []
    for idx, member in enumerate(members):
        cum_points = []
        running_total = 0
        for gw in gws:
            res = GameweekResult.objects.filter(member=member, gameweek=gw).first()
            if res:
                running_total += res.net_points
            cum_points.append(running_total)

        color = color_palette[idx % len(color_palette)]
        points_datasets.append({
            'label': member.manager_name,
            'data': cum_points,
            'borderColor': color,
            'backgroundColor': color,
            'fill': False,
            'tension': 0.3,
        })

    # 2. Net Profit / Loss Leaderboard Data
    leaderboard = get_member_financial_leaderboard()
    pl_labels = [item['member'].manager_name for item in leaderboard]
    pl_data = [float(item['net_pl']) for item in leaderboard]
    pl_colors = ['#10b981' if val >= 0 else '#ef4444' for val in pl_data]

    # 3. Weekly Points Distribution (High, Average, Low)
    weekly_high = []
    weekly_avg = []
    weekly_low = []
    for gw in gws:
        stats = GameweekResult.objects.filter(gameweek=gw).aggregate(
            max_pts=Max('net_points'),
            min_pts=Min('net_points'),
            avg_pts=Avg('net_points')
        )
        weekly_high.append(stats['max_pts'] or 0)
        weekly_avg.append(round(stats['avg_pts'] or 0, 1))
        weekly_low.append(stats['min_pts'] or 0)

    # 4. Pot Distribution
    treasury = get_treasury_summary()
    pots_data = {
        'labels': ['BBQ Pot (Standard + Fines)', 'Jackpot Pot (Season)', 'Weekly Prize Pool (Paid/Active)'],
        'data': [
            float(treasury['total_bbq_pot']),
            float(treasury['total_jackpot_pot']),
            float(treasury['total_prize_pool_collected']),
        ],
        'colors': ['#f59e0b', '#8b5cf6', '#10b981'],
    }

    return JsonResponse({
        'gw_labels': gw_labels,
        'points_datasets': points_datasets,
        'pl_labels': pl_labels,
        'pl_data': pl_data,
        'pl_colors': pl_colors,
        'weekly_high': weekly_high,
        'weekly_avg': weekly_avg,
        'weekly_low': weekly_low,
        'pots': pots_data,
    })
