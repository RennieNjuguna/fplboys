# ⚽ FPL Boys - Mini-League & Financial Ledger Web Application

A complete, production-ready Django web application with an SQLite database backend designed to manage a 10-member Fantasy Premier League (FPL) mini-league (**League ID: 1868934**) and its financial ledger.

---

## 🏆 Core League Specifications

| Specification | Rule & Allocation |
| :--- | :--- |
| **FPL Classic League ID** | `1868934` |
| **Total Members** | 10 managers |
| **Weekly Contribution** | **Ksh. 150** per gameweek per member (Total: Ksh. 1,500/GW) |
| **Contribution Breakdown** | • **Ksh. 50** → End-of-season BBQ Pot (Ksh. 500/GW)<br>• **Ksh. 50** → Weekly Gameweek Prize Pool (Ksh. 500/GW)<br>• **Ksh. 50** → End-of-season Jackpot Pot (Ksh. 500/GW) |
| **Weekly Payout (Top 3, 3:2:1)** | • **1st Place (3/6)**: Ksh. 250.00<br>• **2nd Place (2/6)**: Ksh. 166.67<br>• **3rd Place (1/6)**: Ksh. 83.33 |
| **Tie-Breaker Rule** | Split tied positions equally (e.g. 2-way tie for 1st splits Ksh. 416.67 = Ksh. 208.34 each; 3rd gets Ksh. 83.33) |
| **Late Payment Fine** | **Ksh. 50** automatically assessed if timestamp > GW deadline. **All late fines route directly into the BBQ Pot!** |

---

## 🚀 Quick Start & Installation

### 1. Requirements
* Python 3.7+ (tested on Python 3.7.9)
* Pip

### 2. Setup Virtual Environment & Dependencies
```bash
# Clone or navigate to the project directory
cd c:\WorkArea\fpl_boyz

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Migrations
```bash
python manage.py migrate
```

### 4. Populate Seed Data (10 Members + GW1 Sample Payments)
```bash
python manage.py seed_data
```

### 5. Sync Live Standings from FPL API
```bash
python manage.py sync_fpl
```

### 6. Create Superuser (for Django Admin)
```bash
python manage.py createsuperuser
```

### 7. Run Development Server
```bash
python manage.py runserver 0.0.0.0:8000
```
Open your browser at `http://127.0.0.1:8000/`.

---

## 🖥️ Web Interfaces & Portals

1. **📊 Main Dashboard (`/`)**:
   * Live Pot Balances: **🍖 BBQ Pot** (Base + Late Fines), **🏆 Jackpot Pot**, **💰 Weekly Prizes Paid**, **⚡ Total Revenue**.
   * Gameweek Highlights & Top 3 Podium Cards with cash winnings.
   * Standings summary and recent payment activity feed.
   * Next Gameweek deadline countdown in East Africa Time (EAT).

2. **🏆 Standings Hub (`/standings/`)**:
   * Filter by **Overall Cumulative Points**, **Specific Gameweek (GW 1-38)**, or **Monthly Rankings**.
   * Tabular layout showing Gross Points, Transfer Hits (`-4`), Net Points, Global FPL Rank, and Top 3 Prize Badges.

3. **📑 Financial Ledger Matrix (`/treasury/ledger/`)**:
   * Excel-style interactive 2D matrix (10 Members × 38 Gameweeks).
   * Color-coded status badges:
     * 🟢 **Paid On-Time** (Ksh. 150)
     * 🟡 **Late** (Ksh. 200, includes Ksh. 50 BBQ late fine)
     * 🔴 **Unpaid / Defaulter** (Pending payment for active/finished GW)
     * ⚪ **Upcoming** (Future gameweek)
   * Sticky manager columns and real-time column & row aggregates.

4. **📈 Profit & Performance Analytics (`/analytics/`)**:
   * **Net Profit / Loss Leaderboard**: $\text{Net P/L} = \text{Prizes Won} - (\text{Contributions} + \text{Fines Paid})$.
   * Interactive **Chart.js** visualizations:
     * *Cumulative Points Race* (10 managers line progression)
     * *Cumulative Profit / Loss Bar Chart* (Gainers vs. Losers)
     * *Weekly Points Spread* (High, Average, Low per GW)
     * *Treasury Pot Allocation Doughnut Chart*

5. **💼 Treasurer Fast-Entry Portal (`/treasury/portal/`)**:
   * Rapid M-Pesa payment recording form.
   * **Real-time Deadline Validator**: Warns the treasurer and automatically prompts late-fee inclusion if payment is after the official GW deadline.
   * One-click **"Sync Standings with FPL"** button.
   * Treasury audit trail.

6. **🚨 Defaulters & Reminders Hub (`/treasury/defaulters/`)**:
   * Audit list showing all members with overdue contributions.
   * **One-Click WhatsApp Reminder Generator**: Opens WhatsApp Web / Mobile with a pre-filled friendly reminder message including balance owed and missed GWs.
   * **Click-to-Copy** reminder text button with clipboard toast notification.

7. **⚙️ Django Admin Portal (`/admin/`)**:
   * Mobile-responsive, color-coded administration for Members, Gameweeks, Results, Payments, and Audit Logs.

---

## ⏱️ Background Sync Automation

To automatically synchronize FPL scores and calculate payouts after each gameweek concludes:

### Option A: Windows Task Scheduler
Create a scheduled task running daily or after match hours:
```powershell
powershell -Command "cd C:\WorkArea\fpl_boyz; python manage.py sync_fpl"
```

### Option B: Linux / Cron
```cron
# Run every 6 hours
0 */6 * * * cd /path/to/fpl_boyz && /path/to/venv/bin/python manage.py sync_fpl >> /var/log/fpl_sync.log 2>&1
```

---

## 🧪 Running Automated Tests

Run the full test suite covering tie-breaker payout algorithms, late fine allocations, pot math, and matrix generators:
```bash
python manage.py test
```

---

## 📁 Project Architecture

```
fpl_boyz/
├── manage.py
├── requirements.txt
├── README.md
├── fpl_boys/
│   ├── settings.py           # Core settings, TZ (Africa/Nairobi), constants
│   ├── urls.py               # Main URL dispatcher
│   ├── wsgi.py
│   └── asgi.py
├── league/
│   ├── models.py             # Member, Gameweek, GameweekResult
│   ├── views.py              # Dashboard, Standings Hub, Analytics, Manager profile
│   ├── context_processors.py # Global pot & deadline context
│   ├── services/
│   │   ├── fpl_client.py     # FPL API client & sync processor
│   │   └── payout_engine.py  # 3:2:1 Top 3 prize & tie-breaker calculations
│   ├── management/commands/
│   │   ├── sync_fpl.py       # FPL API synchronization command
│   │   └── seed_data.py      # 10 members & GW1 sample payments seeder
│   └── tests.py              # Payout and tie-breaker unit tests
├── treasury/
│   ├── models.py             # Payment, AuditLog
│   ├── forms.py              # PaymentForm with deadline validation
│   ├── views.py              # Financial ledger matrix, Treasurer portal, Defaulters
│   ├── services/
│   │   ├── ledger_matrix.py  # Excel-style 2D matrix engine
│   │   └── pot_calculator.py # Pot totals (BBQ + fines, Jackpot, Prizes)
│   ├── admin.py              # Custom admin with color badges
│   └── tests.py              # Financial and late fee unit tests
└── templates/
    ├── base.html             # Tailwind CSS & Flowbite/Lucide layout
    ├── dashboard/
    │   ├── index.html        # Main dashboard & pots summary
    │   ├── standings.html    # Standings Hub (Overall, GW, Monthly)
    │   ├── ledger.html       # Excel-style financial ledger matrix
    │   ├── analytics.html    # Chart.js graphs & Net P/L leaderboard
    │   └── manager_profile.html # Individual manager statement
    └── treasury/
        ├── portal.html       # Treasurer Fast M-Pesa entry
        └── defaulters.html   # Defaulter audit & WhatsApp reminder generator
```
