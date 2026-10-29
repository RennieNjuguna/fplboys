import os
import sys
import django
from decimal import Decimal
from django.utils import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
django.setup()

from league.models import Gameweek, Member, GameweekResult
from news.models import RoastEdition, ManagerRoastItem
from news.services.roast_engine import ensure_news_tables_exist
from news.services.gazette_storage import export_edition_to_disk


def publish_gw8():
    ensure_news_tables_exist()
    gw = Gameweek.objects.get(number=8)

    # 1. Update GameweekResult prize allocations:
    # 1st Eligible: Marvin Owino (46 net pts, rolled from Chris) = Ksh. 250.00
    # 2nd Eligible: Benn Mwangi (38 net pts, rolled past Marve) = Ksh. 167.00
    # 3rd Eligible: Renny Muragu (36 net pts, rolled past Erick) = Ksh. 83.00
    # Flagged / Ineligible: King Chris (53p), Marve Mathingu (40p), Erick Muchira (37p), Torque Dennis (34p), Aron Mangati (30p)
    payout_map = {
        'Marvin': Decimal('250.00'),
        'Benn': Decimal('167.00'),
        'Renny': Decimal('83.00'),
    }

    for res in GameweekResult.objects.filter(gameweek=gw).select_related('member'):
        m_name = res.member.manager_name
        prize = Decimal('0.00')
        is_top3 = False
        for k, p in payout_map.items():
            if k in m_name:
                prize = p
                is_top3 = True
                break
        res.gw_prize_won = prize
        res.is_top3 = is_top3
        res.save(update_fields=['gw_prize_won', 'is_top3'])

    # 2. Build Broadsheet Content (The Ghost Town Heist & Defaulters Meltdown)
    headline = "THE GHOST TOWN HEIST: KING CHRIS WINS GW 8 BUT GETS ZERO CASH, BENN POCKETS KSH. 167 WITH A -2 PALMER CAPTAIN, & MARVIN HARVESTS THE GOLD!"
    subheadline = "Issue #8 The Defaulter Catastrophe: Half the league is flagged ineligible as Chris's maiden victory is confiscated, Benn cashes from 4th with 38 points, Renny podiums from 6th with 36, and Don Bosco reigns supreme."
    
    chief_editor = "The League Scribe & Chief Banter Executioner"
    weather_report = "Dense fog over Stamford Bridge, freezing financial sanctions across 5 defaulter compounds, and pure comedy rain showering Odysseus Reign."

    editorial_lead = (
        "Welcome to the ultimate Theatre of the Absurd! Gameweek 8 will be enshrined forever as the week where FPL logic was officially declared deceased. "
        "Consider this sequence of events: King Chris ('The_Painter..')—the laughing stock of the league, author of the 20-point horror show, and the fabled 6-Peat Defaulter—finally took a -4 hit, scored 53 net points, and OUTSCORED THE ENTIRE LEAGUE to win Gameweek 8! "
        "But because he hasn't paid his dues since the stone age, HE GETS ZERO SHILLINGS! His Ksh. 250 championship purse was snatched away and delivered on a silver platter to Marvin Owino ('Don Bosco'), who claimed 1st place cash on 46 points! "
        "But wait, it gets even more outrageous: Benn Mwangi ('Odysseus Reign') CAPTAINED COLE PALMER FOR MINUS TWO POINTS (-2), crawled to 38 net points in 4th place, and STILL WALKED AWAY WITH KSH. 167.00 IN 2ND PLACE CASH! "
        "Why? Because King Chris (1st) and Marve Mathingu (3rd) were BOTH INELIGIBLE! "
        "And to complete the heist, Renny Muragu finished in 6th place with a pitiful 36 points and pocketed Ksh. 83.00 in 3rd place cash because Erick Muchira (5th) was ALSO INELIGIBLE! "
        "With FIVE of our ten managers now living in the Defaulter Ward (Chris, Marve, Erick, Dennis, Aron), the compliant managers are literally picking cash off the floor with scores that belong in the Sunday league!"
    )

    marvin = Member.objects.filter(manager_name__icontains="Marvin").first()
    chris = Member.objects.filter(manager_name__icontains="Chris").first()

    king = marvin
    king_reason = (
        "Marvin 'Don Bosco' Owino proves that paying your dues and running a tight ship is the ultimate FPL superpower! While the defaulters threw away championships, Marvin calmly took 46 net points, collected the confiscated Ksh. 250.00 jackpot, and took his season winnings past Ksh. 660!"
    )

    clown = chris
    clown_reason = (
        "The Greek tragedy to end all Greek tragedies. After 7 weeks of being mocked, relegated, and roasted, King Chris actually built a winning team, scored 53 points, and finished Rank 1 in the league... ONLY TO HAVE HIS KSH. 250 PRIZE SEIZED BY THE TREASURY DUE TO A 6-WEEK DEFAULTING SPREE! The greatest own goal in league history!"
    )

    quote_of_the_week = "\"I captained Cole Palmer for minus two points, scored 38 points, and won Ksh. 167. At this point, I think I could submit an empty team sheet and the treasury would still send me an M-Pesa.\" — Benn Mwangi"
    quote_author = "Benn Mwangi (Odysseus Reign & Master of Unearned Wealth)"

    defaulter_roast = (
        "🚨 TREASURY WALL OF SHAME (GW 8 — HALF THE LEAGUE IN DEFAULT): An astonishing FIVE OUT OF TEN MANAGERS are now officially under treasury sanctions! "
        "King Chris wins the week and donates Ksh. 250 to Marvin. Marve Mathingu wildcards to 40 points in 3rd place and donates Ksh. 167 to Benn. "
        "Erick Muchira lands in 5th on 37 points and donates Ksh. 83 to Renny. Torque Dennis (34 pts) and Aron Mangati (30 pts) complete the defaulter roster. "
        "At this rate, the year-end BBQ will have wagyu steak and a live band, entirely sponsored by Chris and his merry band of defaulters. Pay your fines, gentlemen!"
    )

    transfer_hit_roast = (
        "💥 THE CAPTAINCY CEMETERY & LOW-SCORING CARNAGE: Gameweek 8 saw the lowest scoring average of the season! "
        "Benn Mwangi reached the pinnacle of banter by captaining Cole Palmer for -2 points (Palmer blanked and picked up cards in Chelsea's 0-2 loss to Spurs). "
        "Marve Mathingu activated his WILDCARD chip, captained Martin Odegaard for 6 points, and benched Haaland's armband. "
        "Bright Ottore and Renny Muragu each left 14 points rotting on their benches (both benching Kinsky's 9-point Leeds clean sheet). "
        "Marvin Owino benched 11-point Amar Dedić. And Samuel Wambua benched 9-point Luke O'Nien to crash to 33 points!"
    )

    classifieds = [
        {
            'title': "LOST: King Chris's First-Ever Victory Shillings",
            'desc': "One 1st place prize worth Ksh. 250.00. Won legitimately on the pitch (53 pts), confiscated instantly at the cashier desk. Inquire at the Treasury Fine Vault.",
            'contact': "Call 0800-UNPAID-FINE"
        },
        {
            'title': "MASTERCLASS: How to Win Cash with Negative Points",
            'desc': "Join Benn Mwangi's exclusive seminar on captaining -2 point players, scoring 38 points, and strolling away with Ksh. 167 in 2nd place cash. No skill required.",
            'contact': "Odysseus Roll-Down Agency"
        },
        {
            'title': "FIRE SALE: 14 Benched Kinsky Points",
            'desc': "Bright Ottore and Renny Muragu both had James Kinsky (9 pts) chilling on the pine during Leeds' 0-0 draw. Available for trade to any manager with working vision.",
            'contact': "Benched Keepers Union"
        },
        {
            'title': "TREASURY ANNOUNCEMENT: Defaulting Quorum Reached",
            'desc': "With 50% of the league now flagged as ineligible, compliant managers need only score 35 points to guarantee weekly cash returns. Keep defaulting, boys!",
            'contact': "The Board of Creditors"
        }
    ]

    edition, created = RoastEdition.objects.update_or_create(
        gameweek=gw,
        defaults={
            'edition_number': 8,
            'headline': headline,
            'subheadline': subheadline,
            'publish_date': timezone.now(),
            'chief_editor': chief_editor,
            'weather_report': weather_report,
            'editorial_lead': editorial_lead,
            'clown_of_the_week': clown,
            'clown_reason': clown_reason,
            'king_of_the_week': king,
            'king_reason': king_reason,
            'quote_of_the_week': quote_of_the_week,
            'quote_author': quote_author,
            'defaulter_roast': defaulter_roast,
            'transfer_hit_roast': transfer_hit_roast,
            'classified_ads': classifieds,
            'is_published': True,
        }
    )

    edition.manager_roasts.all().delete()

    roasts_data = [
        # Rank 1 on Pts (Ineligible): King Chris
        {
            'name_match': 'Chris',
            'rank': 1,
            'net_pts': 53,
            'badge': '🤡 1ST ON PTS (THE UNPAID CHAMPION & 6-PEAT DEFAULTER)',
            'title': "King Chris - The Painter Wins GW 8 Outright Only to Watch His Ksh. 250 Confiscated!",
            'body': "YOU CANNOT SCRIPT A MORE DELICIOUS IRONY! After months of being the league punching bag—20 points in GW 5, 48 in GW 6, dead last finishes—King Chris took a -4 hit, captained Erling Haaland (16p), unleashed Marcus Tavernier (10 pts in Bournemouth's 3-0 demolition of Man Utd), David Raya (7p), and Affengruber (6p) to rack up 53 net points and WIN GAMEWEEK 8 OUTRIGHT! But did Chris celebrate with cash? NO! Because Chris is a SIX-PEAT DEFAULTER who hasn't paid his dues in 6 consecutive weeks! The cashier slammed the window shut, declared him INELIGIBLE, and handed his Ksh. 250.00 prize straight to Marvin Owino. Chris won the battle on the pitch and lost the war at the bank!",
            'verdict': "Verdict: The Tragic Champion Who Funded Don Bosco's Victory (Ksh. 0.00)",
        },
        # Rank 2 on Pts (1st Eligible): Marvin Owino
        {
            'name_match': 'Marvin',
            'rank': 2,
            'net_pts': 46,
            'badge': '👑 1ST ELIGIBLE (THE KING OF TREASURY DIVIDENDS)',
            'title': "Marvin Owino - 'Don Bosco' Rolls Into 1st Place Jackpot & Takes Season Haul Past Ksh. 660!",
            'body': "The moral of the story: always pay your league dues! Marvin scored a steady 46 points with captain Haaland (16p), Tavernier (10p), Becker (6p), and King (6p). He even had the luxury of leaving Amar Dedić's 11-point Newcastle clean sheet haul on his bench! On raw points, Marvin was second. But with King Chris barred from entering the bank, Marvin was promoted to 1st place and handed the full Ksh. 250.00 jackpot! That brings Marvin's personal treasury loot to a staggering Ksh. 666.68. The Don Bosco empire continues to feast on defaulter tears!",
            'verdict': "Verdict: Promoted Champion & Master of Good Governance (Ksh. 250.00)",
        },
        # Rank 3 on Pts (Ineligible): Marve Mathingu
        {
            'name_match': 'Marve',
            'rank': 3,
            'net_pts': 40,
            'badge': '🚨 3RD ON PTS (WILDCARD TO NOWHERE & FLAGGED AGAIN)',
            'title': "Marve Mathingu - 'Marve of the Match' Wildcards to 40 Pts, Finishes 3rd, Stays Ineligible!",
            'body': "Marve pulled out the emergency WILDCARD chip to overhaul his struggling squad. The result? A modest 40 points, led by Virgil van Dijk (9p), Haaland (8p), Raya (7p), and Evanilson (6p), while benching Haaland's armband in favor of Martin Odegaard (6p cap). Under normal conditions, finishing 3rd in a low-scoring week would guarantee cash. But Marve remains locked in the Defaulter Ward alongside Chris! His 3rd place cash rolled straight past him into Benn's pockets. Wildcard spent, fines unpaid, cash evaporated.",
            'verdict': "Verdict: Wildcard Redeemed for Zero Shillings in the Penalty Box",
        },
        # Rank 4 on Pts (2nd Eligible): Benn Mwangi
        {
            'name_match': 'Benn',
            'rank': 4,
            'net_pts': 38,
            'badge': '💰 2ND ELIGIBLE (THE -2 PALMER CAPTAINCY CON ARTIST)',
            'title': "Benn Mwangi - 'Odysseus Reign' Captains -2 pt Palmer, Scores 38 Pts, & Banks Ksh. 167!",
            'body': "LADIES AND GENTLEMEN, WE HAVE WITNESSED THE GREATEST FPL HEIST OF ALL TIME! Benn Mwangi handed the captain's armband to Cole Palmer. Palmer proceeded to blank and get booked in Chelsea's 0-2 loss to Spurs, handing Benn a majestic MINUS TWO POINTS (-2)! Benn crawled across the finish line with a miserable 38 net points in 4th place. But because King Chris (1st) and Marve (3rd) were both flagged as defaulters, Benn rolled straight into 2nd place cash and pocketed KSH. 167.00! That's back-to-back weeks of Benn collecting cash from 6th and 4th place. Ezri Konsa's 14-pointer literally fed him silver!",
            'verdict': "Verdict: The Greatest Roll-Down Bandit in Human History (Ksh. 167.00)",
        },
        # Rank 5 on Pts (Ineligible): Erick Muchira
        {
            'name_match': 'Erick',
            'rank': 5,
            'net_pts': 37,
            'badge': '🚨 5TH ON PTS (FROZEN OUT OF THE CASH CASCADE)',
            'title': "Erick Muchira - 'mambaaa' Manages 37 Pts But Stays Frozen in the Defaulters Ward",
            'body': "For the second straight week, Erick found himself watching the roll-down money train bypass him entirely. Erick scored 37 points with Haaland cap (16p) and Bogle (5p), finishing 5th. Had Erick been in good standing with the treasurer, he would have been right on the edge of the prize money when Chris and Marve were disqualified. Instead, his red 'INELIGIBLE' flag meant the money skipped him and landed right in Renny Muragu's lap. Two weeks of self-inflicted financial embargo!",
            'verdict': "Verdict: Blocked by Treasury Sanctions as Renny Collects His Cash",
        },
        # Rank 6 on Pts (3rd Eligible): Renny Muragu
        {
            'name_match': 'Renny',
            'rank': 6,
            'net_pts': 36,
            'badge': '🥉 3RD ELIGIBLE (THE 36-POINT PODIUM MIRACLE)',
            'title': "Renny Muragu - 'The Young Ones' Benches 14 Pts, Scores 36, and Takes 3rd Place Cash!",
            'body': "You could not make this up if you tried! Renny had an absolute stinker of a gameweek: he left 14 points on his bench (including James Kinsky's 9-point Leeds clean sheet), watched Cherki (0p), Groß (0p), and De Cuyper (1p) fail, and limped home with just 36 net points in 6th place. But with Chris (1st), Marve (3rd), and Erick (5th) ALL DISQUALIFIED ahead of him, Renny was magically promoted onto the podium for Ksh. 83.00! Renny now has two podium cash payouts this season while scoring 55 and 36 points. Pure unadulterated jam!",
            'verdict': "Verdict: Promoted to the Podium from 6th Place with 36 Points (Ksh. 83.00)",
        },
        # Rank 7 (Ineligible): Torque Dennis
        {
            'name_match': 'Dennis',
            'rank': 7,
            'net_pts': 34,
            'badge': '💸 7TH ON PTS (POST-TRIPLE CAPTAIN HANGOVER & STILL FINED)',
            'title': "Torque Dennis - 'DenniSkills' Slumps to 34 Pts and Remains in the Defaulter Doghouse",
            'body': "After the heartbreak of GW 7 where his 75-point Triple Captain earned him zero shillings due to fines, Dennis suffered a massive post-chip hangover. He scored just 34 points, benched 12 points (including Petrović 7p), and watched Mbeumo (2p), Rogers (1p), and Guéhi (0p) disappear. More importantly, Dennis is STILL FLAGGED on the defaulters ledger! No points, no cash, and a growing fine tab.",
            'verdict': "Verdict: Triple Captain Burned Last Week, Cold Beans and Fines This Week",
        },
        # Rank 8: Samuel Wambua
        {
            'name_match': 'Samuel',
            'rank': 8,
            'net_pts': 33,
            'badge': '📉 8TH PLACE (THE REIGN OF TERROR COMES CRASHING DOWN)',
            'title': "Samuel Wambua - 'maggry shiners' Suffers 33-pt Hangover & Benches 9-pt O'Nien",
            'body': "The streak is broken! After four glorious, cash-drenched weeks on the podium (GW 4, 5, 6, and 7), Samuel finally fell back to earth with an almighty thud. Beyond captain Haaland (16p) and Bogle (5p), his team went completely cold: Cherki (0p), Groß (0p), Rogers (1p), Schade (2p). To make matters worse, Samuel left Luke O'Nien's 9-point Sunderland clean sheet haul on his bench! Crashing to 33 points in 8th place, Samuel takes his first week off from collecting cash since August.",
            'verdict': "Verdict: 4-Week Podium Empire Brought Down by a Sunderland Bench Blunder",
        },
        # Rank 9 on Pts (Ineligible): Aron Mangati
        {
            'name_match': 'Aron',
            'rank': 9,
            'net_pts': 30,
            'badge': '🧊 TIED 9TH ON PTS (ROCK BOTTOM & FLAGGED)',
            'title': "Aron Mangati - 'Arons' Slumps to 30 Pts and Lands on the Ineligible Blacklist",
            'body': "Things have gone from bad to worse for Aron. In GW 6, he missed cash by 1 point due to benching De Cuyper. In GW 7, he sank to 59 points. In GW 8, he hit rock bottom with just 30 net points: Christie (1p), Rogers (1p), Cherki (0p), Calvert-Lewin (2p), Donnarumma (1p). And to complete his misery, Aron made his official debut on the TREASURY WALL OF SHAME as an INELIGIBLE DEFAULTER! Tied for last place and fined. A week to delete from the memory banks.",
            'verdict': "Verdict: Dead Last on Points and Trapped in the Defaulter Ward",
        },
        # Rank 9 on Pts (Eligible): Bright Ottore
        {
            'name_match': 'Bright',
            'rank': 9,
            'net_pts': 30,
            'badge': '🪑 TIED 9TH PLACE (THE BENCH HOARDING RELAPSE: 14 PTS)',
            'title': "Bright Ottore - 'Phill Me In' Relapses with 14 Benched Pts & Palmer Minus-Point Stinker!",
            'body': "Just when we thought Bright had cured his bench-hoarding addiction, he suffered a catastrophic relapse! Bright left a massive 14 points on his pine—including James Kinsky's 9-point clean sheet for Leeds and Sangaré's 4 points. On the pitch, Cole Palmer scored MINUS ONE (-1), Cherki got 0, Groß got 0, and Gonzalo got 2. Tied for last place on 30 points, Bright's two-week cash honeymoon came to an abrupt, screeching halt.",
            'verdict': "Verdict: Chronic Bench Hoarding Returns with a Vengeance",
        },
    ]

    for idx, rdata in enumerate(roasts_data):
        member = Member.objects.filter(manager_name__icontains=rdata['name_match']).first()
        if not member:
            continue

        ManagerRoastItem.objects.create(
            edition=edition,
            member=member,
            rank_in_gw=rdata['rank'],
            net_points=rdata['net_pts'],
            badge=rdata['badge'],
            roast_title=rdata['title'],
            roast_body=rdata['body'],
            verdict=rdata['verdict'],
            order=idx + 1
        )

    export_edition_to_disk(edition)
    print(f"[SUCCESS] Gazette Issue #{edition.edition_number} for GW {gw.number} published and exported to news/editions/gw8.json successfully!")


if __name__ == '__main__':
    publish_gw8()
