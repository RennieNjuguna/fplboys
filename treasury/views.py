from decimal import Decimal
import urllib.parse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import pytz

from league.models import Member, Gameweek, GameweekResult
from league.services.fpl_client import FPLSyncService
from treasury.models import Payment, AuditLog, TreasuryConfig, PrizePayout, PaymentTransaction

from treasury.forms import PaymentForm, LogMpesaPaymentForm
from treasury.services.ledger_matrix import build_financial_ledger_matrix, get_active_gw_flagged_summary

from treasury.services.pot_calculator import get_treasury_summary, get_member_financial_leaderboard
from treasury.decorators import treasury_admin_required
from treasury.services.payment_allocation import (
    process_bulk_payment_carryover,
    apply_winnings_to_future_gameweeks,
    get_member_available_prize_balance,
    record_cash_payout,
    allocate_payment_with_rollover
)






def treasury_unlock_view(request):
    """
    Password protection gate for Treasury Admin Portal & CRUD actions.
    Validates against TreasuryConfig admin password in DB (default: @FPLBoyz254??).
    Remembers session permanently (1 year expiry) on the device.
    """
    next_url = request.GET.get('next') or request.POST.get('next') or '/treasury/portal/'

    if request.user.is_authenticated or request.session.get('treasury_admin_authenticated'):
        return redirect(next_url)

    if request.method == 'POST':
        password = request.POST.get('password', '')
        config = TreasuryConfig.get_config()

        if config.check_admin_password(password):
            request.session['treasury_admin_authenticated'] = True
            # Remember on device for 1 year (31,536,000 seconds)
            request.session.set_expiry(31536000)

            AuditLog.objects.create(
                action='TREASURY_UNLOCKED',
                description="Treasury portal unlocked via admin password authentication (device session remembered).",
                performed_by='Admin User'
            )
            messages.success(request, "🔓 Admin Access Granted! Device remembered.")
            return redirect(next_url)
        else:
            messages.error(request, "❌ Incorrect Admin Password. Access Denied.")

    context = {
        'next': next_url,
    }
    return render(request, 'treasury/unlock.html', context)


def treasury_lock_view(request):
    """
    Locks the treasury section and clears admin session authentication.
    """
    if 'treasury_admin_authenticated' in request.session:
        del request.session['treasury_admin_authenticated']
    messages.info(request, "🔒 Treasury Admin Section is now locked.")
    return redirect('dashboard')


def financial_ledger_view(request):
    """
    Publicly accessible Financial Ledger split into 2 views/tabs:
    1. GW Contributions (Matrix grid of Members x GW payments, fines, with large GW Totals)
    2. Earnings (Leaderboard of Total Paid, Fines, Prizes Won, Net P/L, plus interactive analytics charts)
    Includes Active Gameweek Flagged & Ticking Bomb Radar.
    """
    active_tab = request.GET.get('tab', 'contributions')  # 'contributions' or 'earnings'
    selected_gw = request.GET.get('radar_gw')
    
    matrix_data = build_financial_ledger_matrix(max_gws=38)
    treasury = get_treasury_summary()
    earnings_leaderboard = get_member_financial_leaderboard()
    flagged_summary = get_active_gw_flagged_summary(target_gw_num=selected_gw)

    context = {
        'active_tab': active_tab,
        'matrix': matrix_data,
        'treasury': treasury,
        'earnings_leaderboard': earnings_leaderboard,
        'flagged_summary': flagged_summary,
    }
    return render(request, 'dashboard/ledger.html', context)


@treasury_admin_required
def treasurer_portal_view(request):
    """
    Treasurer Fast Entry Portal to log M-Pesa payments, manage transactions,
    automatically cascade lump-sum carryovers, and rollover prize winnings into future gameweeks.
    """
    members = list(Member.objects.filter(is_active=True).order_by('manager_name'))
    all_gws = Gameweek.objects.all().order_by('number')

    if request.method == 'POST':
        action = request.POST.get('action', 'save_payment')

        if action == 'sync_fpl':
            try:
                service = FPLSyncService()
                service.sync_gameweeks()
                service.sync_members()
                res = service.sync_gameweek_results()
                messages.success(request, f"FPL data synced! Updated {res['results_updated']} scores.")
            except Exception as e:
                messages.error(request, f"FPL sync error: {e}")
            return redirect('treasurer_portal')

        elif action == 'generate_roasts':
            try:
                from news.services.roast_engine import ensure_news_tables_exist, generate_roast_edition
                ensure_news_tables_exist()

                from django.core.management import call_command
                try:
                    call_command('migrate', interactive=False)
                except Exception:
                    pass

                gws_with_results = Gameweek.objects.filter(results__isnull=False).distinct().order_by('number')
                count = 0
                for gw in gws_with_results:
                    try:
                        generate_roast_edition(gw, force_update=True)
                        count += 1
                    except Exception:
                        pass

                if count > 0:
                    messages.success(request, f"📰 Published {count} Gazette issue(s) successfully!")
                else:
                    latest_gw = Gameweek.objects.filter(status__in=['finished', 'active']).order_by('-number').first()
                    if latest_gw:
                        ed = generate_roast_edition(latest_gw, force_update=True)
                        messages.success(request, f"📰 Published The Gazette Issue #{ed.edition_number} for GW {latest_gw.number}!")
                    else:
                        messages.warning(request, "No gameweek results found. Make sure to sync with FPL first.")
            except Exception as e:
                messages.error(request, f"Error publishing Gazette: {e}")
            return redirect('treasurer_portal')

        elif action == 'delete_issue':
            edition_id = request.POST.get('edition_id')
            if edition_id:
                try:
                    from news.models import RoastEdition
                    ed = RoastEdition.objects.get(pk=edition_id)
                    ed_num = ed.edition_number
                    ed.delete()
                    messages.success(request, f"🗑️ Deleted Gazette Issue #{ed_num}.")
                except Exception as e:
                    messages.error(request, f"Error deleting issue: {e}")
            return redirect('treasurer_portal')

        elif action == 'disburse_payout':
            member_id = request.POST.get('member_id')
            amount_str = request.POST.get('amount_to_disburse')
            mpesa_ref = request.POST.get('mpesa_reference', '').strip().upper()
            notes = request.POST.get('notes', '').strip()

            try:
                member = get_object_or_404(Member, pk=member_id)
                amount = Decimal(amount_str)
                payout = record_cash_payout(
                    member=member,
                    amount=amount,
                    mpesa_reference=mpesa_ref,
                    notes=notes
                )
                messages.success(
                    request,
                    f"💸 Recorded M-Pesa cash payout of Ksh. {amount:,.2f} to {member.manager_name}! (Ref: {mpesa_ref or 'N/A'})"
                )
            except Exception as e:
                messages.error(request, f"Error recording cash payout: {e}")
            return redirect('treasurer_portal')

        elif action == 'apply_winnings':
            # Manager using prize winnings to fund future gameweeks
            member_id = request.POST.get('member_id')
            amount_str = request.POST.get('amount_to_apply', '150.00')
            start_gw_str = request.POST.get('start_gw')

            try:
                member = get_object_or_404(Member, pk=member_id)
                amount = Decimal(amount_str)
                start_gw_num = int(start_gw_str) if start_gw_str else None

                applied = apply_winnings_to_future_gameweeks(member, amount, start_gw_num)
                messages.success(
                    request,
                    f"🏆 Successfully applied Ksh. {amount:,.2f} from {member.manager_name}'s prize winnings across {len(applied)} gameweeks!"
                )
            except Exception as e:
                messages.error(request, f"Error applying winnings: {e}")
            return redirect('treasurer_portal')


        elif action == 'save_payment':
            form = LogMpesaPaymentForm(request.POST)
            if form.is_valid():
                amount_paid = form.cleaned_data['amount_paid']
                member = form.cleaned_data['member']
                timestamp_received = form.cleaned_data['timestamp_received']
                mpesa_code = form.cleaned_data['mpesa_code']
                notes = form.cleaned_data['notes']
                verified = form.cleaned_data.get('verified', True)

                # Process payment using unified FIFO allocation engine starting from earliest unpaid/partial GW
                created_payments = allocate_payment_with_rollover(
                    member=member,
                    start_gw=None,
                    total_amount=amount_paid,
                    timestamp=timestamp_received,
                    mpesa_code=mpesa_code,
                    notes=notes,
                    verified=verified,
                    is_prize=False
                )

                if len(created_payments) > 1:
                    first_gw_num = created_payments[0].gameweek.number
                    last_gw_num = created_payments[-1].gameweek.number
                    messages.success(
                        request,
                        f"✅ Payment of Ksh. {amount_paid:,.2f} recorded for {member.manager_name}! Auto-allocated across {len(created_payments)} gameweeks (GW {first_gw_num} to GW {last_gw_num}) in sequential FIFO order."
                    )
                elif created_payments:
                    payment = created_payments[0]
                    late_text = " (⚠️ Late fine of Ksh. 50 added to BBQ pot)" if payment.is_late else ""
                    messages.success(
                        request,
                        f"✅ Recorded payment of Ksh. {amount_paid:,.2f} for {payment.member.manager_name} (GW {payment.gameweek.number}){late_text}."
                    )
                else:
                    messages.info(request, f"Payment recorded for {member.manager_name}.")

                return redirect('treasurer_portal')
            else:
                messages.error(request, "Please correct the errors in the payment form.")

    else:
        form = LogMpesaPaymentForm()

    all_transactions = PaymentTransaction.objects.select_related('member', 'starting_gameweek').prefetch_related('allocations', 'allocations__gameweek').order_by('-timestamp_received', '-created_at')
    all_payments = Payment.objects.select_related('member', 'gameweek', 'transaction').order_by('-timestamp_received', '-created_at')
    audit_logs = AuditLog.objects.all().order_by('-created_at')[:10]
    treasury = get_treasury_summary()

    # Members with their available prize balances
    from treasury.services.payment_allocation import get_member_available_prize_balance, models_sum
    prize_payouts = PrizePayout.objects.filter(payout_method='MPESA_CASH').select_related('member', 'gameweek').order_by('-disbursed_at')[:20]

    members_winnings_list = []
    for m in members:
        avail = get_member_available_prize_balance(m)
        cash_paid = PrizePayout.objects.filter(member=m, payout_method='MPESA_CASH').aggregate(total=models_sum('amount'))['total'] or Decimal('0.00')
        reinvested = PrizePayout.objects.filter(member=m, payout_method='REINVESTED').aggregate(total=models_sum('amount'))['total'] or Decimal('0.00')
        members_winnings_list.append({
            'member': m,
            'available_winnings': avail,
            'total_won': m.total_prizes_won,
            'cash_disbursed': cash_paid,
            'reinvested': reinvested,
        })

    # Gazette editions list for management
    gazette_editions = []
    try:
        from news.models import RoastEdition
        gazette_editions = list(RoastEdition.objects.select_related('gameweek').order_by('-edition_number'))
    except Exception:
        pass

    context = {
        'form': form,
        'all_transactions': all_transactions,
        'all_payments': all_payments,
        'prize_payouts': prize_payouts,
        'audit_logs': audit_logs,
        'treasury': treasury,
        'members_winnings_list': members_winnings_list,
        'all_gws': all_gws,
        'gazette_editions': gazette_editions,
    }
    return render(request, 'treasury/portal.html', context)




@treasury_admin_required
def payment_edit_view(request, payment_id):
    """
    Edit / Update an existing Payment record.
    If updated amount exceeds standard Ksh. 150.00, caps current GW at 150 and rolls over excess to next GWs.
    """
    payment = get_object_or_404(Payment, pk=payment_id)

    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            new_amount = form.cleaned_data['amount_paid']
            member = form.cleaned_data['member']
            gameweek = form.cleaned_data['gameweek']
            timestamp = form.cleaned_data['timestamp_received']
            mpesa_code = form.cleaned_data['mpesa_code']
            notes = form.cleaned_data['notes']
            verified = form.cleaned_data.get('verified', True)

            standard_rate = Decimal('150.00')
            if new_amount > standard_rate:
                # Cap this payment at 150 and rollover excess to next GWs
                payment.amount_paid = standard_rate
                payment.timestamp_received = timestamp
                payment.mpesa_code = mpesa_code
                payment.notes = notes
                payment.verified = verified
                payment.save()

                excess = new_amount - standard_rate
                next_gw = Gameweek.objects.filter(number__gt=gameweek.number).order_by('number').first()
                if next_gw and excess > Decimal('0.00'):
                    allocate_payment_with_rollover(
                        member=member,
                        start_gw=next_gw,
                        total_amount=excess,
                        timestamp=timestamp,
                        mpesa_code=mpesa_code,
                        notes=f"Excess rollover from GW {gameweek.number} payment edit",
                        verified=verified,
                        is_prize=False
                    )

                AuditLog.objects.create(
                    action='PAYMENT_UPDATED',
                    description=f"Updated payment ID #{payment.id} for {member.manager_name} (GW {gameweek.number}) to Ksh. 150.00 and rolled over Ksh. {excess:,.2f} to future GWs.",
                    performed_by='Treasurer'
                )
                messages.success(request, f"✅ Payment for {member.manager_name} (GW {gameweek.number}) capped at Ksh. 150.00, and excess Ksh. {excess:,.2f} rolled over to subsequent GWs.")
            else:
                updated_payment = form.save()
                AuditLog.objects.create(
                    action='PAYMENT_UPDATED',
                    description=f"Updated payment ID #{updated_payment.id} for {updated_payment.member.manager_name} (GW {updated_payment.gameweek.number}) to Ksh. {updated_payment.amount_paid}.",
                    performed_by='Treasurer'
                )
                messages.success(request, f"✅ Payment for {updated_payment.member.manager_name} (GW {updated_payment.gameweek.number}) updated successfully.")
            return redirect('treasurer_portal')
    else:
        # Pre-format datetime-local for input
        initial_ts = payment.timestamp_received.strftime('%Y-%m-%dT%H:%M') if payment.timestamp_received else ''
        form = PaymentForm(instance=payment, initial={'timestamp_received': initial_ts})

    context = {
        'form': form,
        'payment': payment,
    }
    return render(request, 'treasury/payment_edit.html', context)


@treasury_admin_required
def payment_delete_view(request, payment_id):
    """
    Delete a Payment record.
    """
    payment = get_object_or_404(Payment, pk=payment_id)
    member_name = payment.member.manager_name
    gw_num = payment.gameweek.number
    amount = payment.amount_paid

    if request.method == 'POST':
        payment.delete()
        AuditLog.objects.create(
            action='PAYMENT_DELETED',
            description=f"Deleted payment ID #{payment_id} for {member_name} (GW {gw_num}, Ksh. {amount}).",
            performed_by='Treasurer'
        )
        messages.success(request, f"🗑️ Payment for {member_name} (GW {gw_num}, Ksh. {amount}) has been deleted.")
        return redirect('treasurer_portal')

    context = {
        'payment': payment,
    }
    return render(request, 'treasury/payment_confirm_delete.html', context)


@treasury_admin_required
def transaction_delete_view(request, transaction_id):
    """
    Delete a PaymentTransaction and all its associated per-GW allocations.
    """
    tx = get_object_or_404(PaymentTransaction, pk=transaction_id)
    member_name = tx.member.manager_name
    amount = tx.amount
    ref = tx.mpesa_code

    if request.method == 'POST':
        tx.delete()
        AuditLog.objects.create(
            action='PAYMENT_DELETED',
            description=f"Deleted M-Pesa transaction ID #{transaction_id} for {member_name} (Ksh. {amount}, Ref: {ref}) and all its GW allocations.",
            performed_by='Treasurer'
        )
        messages.success(request, f"🗑️ Deleted M-Pesa transaction of Ksh. {amount:,.2f} for {member_name} (Ref: {ref or 'N/A'}).")
        return redirect('treasurer_portal')

    context = {
        'transaction': tx,
    }
    return render(request, 'treasury/transaction_confirm_delete.html', context)


@treasury_admin_required
def payout_delete_view(request, payout_id):
    """
    Deletes a recorded cash prize disbursement (M-Pesa payout)
    and restores that money back to the winner's available prize balance.
    """
    payout = get_object_or_404(PrizePayout, pk=payout_id)
    winner_name = payout.member.manager_name
    amount = payout.amount
    ref = payout.mpesa_reference

    if request.method == 'POST':
        payout.delete()
        AuditLog.objects.create(
            action='PRIZE_PAYOUT_DELETED',
            description=f"Deleted cash prize disbursement of Ksh. {amount:,.2f} for {winner_name} (Ref: {ref or 'N/A'}). Returned Ksh. {amount:,.2f} to winner's available balance.",
            performed_by='Treasurer'
        )
        messages.success(request, f"🗑️ Deleted cash prize disbursement of Ksh. {amount:,.2f} for {winner_name}. Ksh. {amount:,.2f} returned to available prize balance.")
        return redirect('treasurer_portal')

    context = {
        'payout': payout,
    }
    return render(request, 'treasury/payout_confirm_delete.html', context)


@treasury_admin_required
def api_check_deadline(request):
    """
    AJAX endpoint to check payment status and provide smart FIFO previews.
    If gw_id is not provided, automatically resolves to the member's earliest
    unpaid or partially-paid gameweek in sequential FIFO order.
    """
    gw_id = request.GET.get('gw_id')
    member_id = request.GET.get('member_id')
    timestamp_str = request.GET.get('timestamp')

    member = None
    if member_id:
        try:
            member = Member.objects.get(pk=member_id)
        except (Member.DoesNotExist, ValueError):
            member = None

    if timestamp_str:
        try:
            ts = parse_datetime(timestamp_str)
            if timezone.is_naive(ts):
                eat_tz = pytz.timezone('Africa/Nairobi')
                ts = eat_tz.localize(ts)
        except Exception:
            ts = timezone.now()
    else:
        ts = timezone.now()

    standard_due = Decimal('150.00')

    # Resolve target gameweek
    gw = None
    if gw_id:
        try:
            gw = Gameweek.objects.get(pk=gw_id)
        except (Gameweek.DoesNotExist, ValueError):
            gw = None

    if not gw and member:
        # Auto-detect earliest unpaid / partial gameweek for member
        joined_gw = getattr(member, 'joined_gameweek', 1)
        for g in Gameweek.objects.filter(number__gte=joined_gw).order_by('number'):
            p = Payment.objects.filter(member=member, gameweek=g, verified=True).first()
            paid = p.amount_paid if p else Decimal('0.00')
            if paid < standard_due:
                gw = g
                break
        if not gw:
            gw = Gameweek.objects.filter(number__gte=joined_gw).order_by('-number').first()

    if not gw:
        gw = Gameweek.objects.filter(status__in=['active', 'upcoming']).order_by('number').first() or Gameweek.objects.first()

    if not gw:
        return JsonResponse({'error': 'No gameweek available'}, status=400)

    is_waived = gw.number in (1, 2, 19, 38)
    is_late = False
    if gw.start_time and ts and not is_waived:
        is_late = ts > gw.start_time

    late_fine = Decimal('50.00') if is_late else Decimal('0.00')

    existing_paid = Decimal('0.00')
    has_existing = False
    if member:
        existing_p = Payment.objects.filter(member=member, gameweek=gw).first()
        if existing_p:
            existing_paid = existing_p.amount_paid
            has_existing = True

    balance_due = max(Decimal('0.00'), standard_due - existing_paid)

    # Recommended amount
    if has_existing and balance_due > Decimal('0.00'):
        recommended_amount = balance_due
    elif is_late:
        recommended_amount = Decimal('200.00')
    else:
        recommended_amount = standard_due

    eat_tz = pytz.timezone('Africa/Nairobi')
    dl_local = gw.start_time_eat.strftime('%b %d, %Y at %I:%M %p EAT') if gw.start_time else 'N/A'

    if member and has_existing and existing_paid < standard_due:
        msg = f"ℹ️ {member.manager_name} has existing partial payment of Ksh. {existing_paid:,.2f} on {gw.name}. New payment will complete {gw.name} (Bal: Ksh. {balance_due:,.2f}) and cascade any excess to next GWs via FIFO."
    elif member and not has_existing:
        joined_note = f" (joined GW {member.joined_gameweek})" if getattr(member, 'joined_gameweek', 1) > 1 and gw.number == member.joined_gameweek else ""
        msg = f"ℹ️ Auto FIFO: Payment for {member.manager_name} will start sequentially at {gw.name}{joined_note} and cascade in Ksh. 150 increments across future unpaid GWs."
    elif is_waived:
        waiver_reason = {
            1: "Season Kickoff Waiver",
            2: "Early Season Setup Waiver",
            19: "Mid-Season Holiday Waiver",
            38: "Season Finale Waiver",
        }.get(gw.number, "Waiver Gameweek")
        msg = f"🎁 {gw.name} Fine Waiver ({waiver_reason}): No late fine applies."
    elif is_late:
        msg = f"⚠️ Payment timestamp is after {gw.name} start / kickoff ({dl_local}). Ksh. 50 Late Fine applied (Total: Ksh. 200)."
    else:
        msg = f"✅ On-time FIFO payment starting at {gw.name} (Kickoff: {dl_local})."

    return JsonResponse({
        'is_late': is_late,
        'is_waived': is_waived,
        'has_existing': has_existing,
        'existing_paid': float(existing_paid),
        'balance_due': float(balance_due),
        'gw_name': gw.name,
        'gw_number': gw.number,
        'deadline_str': dl_local,
        'late_fine': float(late_fine),
        'recommended_amount': float(recommended_amount),
        'message': msg
    })

