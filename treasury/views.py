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
from treasury.models import Payment, AuditLog, TreasuryConfig, PrizePayout

from treasury.forms import PaymentForm
from treasury.services.ledger_matrix import build_financial_ledger_matrix

from treasury.services.pot_calculator import get_treasury_summary, get_member_financial_leaderboard
from treasury.decorators import treasury_admin_required
from treasury.services.payment_allocation import process_bulk_payment_carryover, apply_winnings_to_future_gameweeks, get_member_available_prize_balance, record_cash_payout






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
    """
    active_tab = request.GET.get('tab', 'contributions')  # 'contributions' or 'earnings'
    matrix_data = build_financial_ledger_matrix(max_gws=38)
    treasury = get_treasury_summary()
    earnings_leaderboard = get_member_financial_leaderboard()

    context = {
        'active_tab': active_tab,
        'matrix': matrix_data,
        'treasury': treasury,
        'earnings_leaderboard': earnings_leaderboard,
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
            form = PaymentForm(request.POST)
            if form.is_valid():
                amount_paid = form.cleaned_data['amount_paid']
                member = form.cleaned_data['member']
                gameweek = form.cleaned_data['gameweek']
                timestamp_received = form.cleaned_data['timestamp_received']
                mpesa_code = form.cleaned_data['mpesa_code']
                notes = form.cleaned_data['notes']
                verified = form.cleaned_data.get('verified', True)

                # Check if this is an excess payment (>150 or >200 if late)
                is_late_gw = (
                    gameweek.number not in (1, 2, 19, 38)
                    and timestamp_received
                    and gameweek.deadline_time
                    and timestamp_received > gameweek.deadline_time
                )
                required_due = Decimal('200.00') if is_late_gw else Decimal('150.00')

                if amount_paid > required_due or (amount_paid > Decimal('150.00') and not is_late_gw):
                    # Excess lump-sum payment -> distribute across starting GW and subsequent gameweeks
                    created_payments = process_bulk_payment_carryover(
                        member=member,
                        start_gw=gameweek,
                        total_amount=amount_paid,
                        timestamp=timestamp_received,
                        mpesa_code=mpesa_code,
                        notes=notes
                    )
                    messages.success(
                        request,
                        f"✅ Payment of Ksh. {amount_paid:,.2f} recorded for {member.manager_name}! Disbursed across {len(created_payments)} gameweeks starting GW {gameweek.number}."
                    )
                else:
                    # Single payment or top-up for this gameweek
                    existing = Payment.objects.filter(member=member, gameweek=gameweek).first()
                    if existing:
                        existing.amount_paid = amount_paid
                        existing.timestamp_received = timestamp_received
                        if mpesa_code:
                            existing.mpesa_code = mpesa_code
                        if notes:
                            existing.notes = notes
                        existing.verified = verified
                        existing.save()
                        payment = existing
                    else:
                        payment = form.save()

                    late_text = " (⚠️ Late fine of Ksh. 50 added to BBQ pot)" if payment.is_late else ""
                    messages.success(
                        request,
                        f"✅ Recorded payment of Ksh. {payment.amount_paid} for {payment.member.manager_name} (GW {payment.gameweek.number}){late_text}."
                    )
                    AuditLog.objects.create(
                        action='PAYMENT_CREATED',
                        description=f"Recorded payment of Ksh. {payment.amount_paid} for {payment.member.manager_name} (GW {payment.gameweek.number}). Code: {payment.mpesa_code}",
                        performed_by='Treasurer'
                    )
                return redirect('treasurer_portal')
            else:
                messages.error(request, "Please correct the errors in the payment form.")

    else:
        form = PaymentForm()

    all_payments = Payment.objects.select_related('member', 'gameweek').order_by('-timestamp_received', '-created_at')
    audit_logs = AuditLog.objects.all().order_by('-created_at')[:10]
    treasury = get_treasury_summary()

    # Members with their available prize balances
    from treasury.services.payment_allocation import get_member_available_prize_balance, models_sum
    prize_payouts = PrizePayout.objects.select_related('member', 'gameweek').order_by('-disbursed_at')[:20]

    members_winnings_list = []
    for m in members:
        avail = get_member_available_prize_balance(m)
        cash_paid = PrizePayout.objects.filter(member=m, payout_method='MPESA_CASH').aggregate(total=models_sum('amount'))['total'] or Decimal('0.00')
        reinvested = Payment.objects.filter(member=m, mpesa_code__icontains="PRIZE", verified=True).aggregate(total=models_sum('amount_paid'))['total'] or Decimal('0.00')
        members_winnings_list.append({
            'member': m,
            'available_winnings': avail,
            'total_won': m.total_prizes_won,
            'cash_disbursed': cash_paid,
            'reinvested': reinvested,
        })

    context = {
        'form': form,
        'all_payments': all_payments,
        'prize_payouts': prize_payouts,
        'audit_logs': audit_logs,
        'treasury': treasury,
        'members_winnings_list': members_winnings_list,
        'all_gws': all_gws,
    }
    return render(request, 'treasury/portal.html', context)




@treasury_admin_required
def payment_edit_view(request, payment_id):
    """
    Edit / Update an existing Payment record.
    """
    payment = get_object_or_404(Payment, pk=payment_id)

    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
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
def api_check_deadline(request):
    """
    AJAX endpoint to check if a chosen timestamp is after the GW deadline.
    """
    gw_id = request.GET.get('gw_id')
    timestamp_str = request.GET.get('timestamp')

    if not gw_id:
        return JsonResponse({'error': 'Missing gw_id'}, status=400)

    try:
        gw = Gameweek.objects.get(pk=gw_id)
    except Gameweek.DoesNotExist:
        return JsonResponse({'error': 'Gameweek not found'}, status=404)

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

    is_waived = gw.number in (1, 2, 19, 38)
    is_late = False
    if gw.deadline_time and ts and not is_waived:
        is_late = ts > gw.deadline_time

    late_fine = Decimal('50.00') if is_late else Decimal('0.00')
    recommended_amount = Decimal('200.00') if is_late else Decimal('150.00')

    eat_tz = pytz.timezone('Africa/Nairobi')
    dl_local = gw.deadline_time.astimezone(eat_tz).strftime('%b %d, %Y at %I:%M %p EAT') if gw.deadline_time else 'N/A'

    if is_waived:
        waiver_reason = {
            1: "Start of the season waiver",
            2: "Teams not yet set up waiver",
            19: "Middle of the season waiver",
            38: "End of the season waiver",
        }.get(gw.number, "Waiver Gameweek")
        msg = f"🎁 {gw.name} Fine Waiver ({waiver_reason}): No late fine applies (Standard: Ksh. 150)."
    elif is_late:
        msg = f"⚠️ Payment timestamp is after {gw.name} deadline ({dl_local}). Ksh. 50 Late Fine applied (Total: Ksh. 200)."
    else:
        msg = f"✅ On-time payment for {gw.name} (Deadline: {dl_local})."

    return JsonResponse({
        'is_late': is_late,
        'is_waived': is_waived,
        'gw_name': gw.name,
        'deadline_str': dl_local,
        'late_fine': float(late_fine),
        'recommended_amount': float(recommended_amount),
        'message': msg
    })

