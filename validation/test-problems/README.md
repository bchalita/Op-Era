# Scaffolding Tests — Simulated Client Data

Testing the model's ability to go from realistic, messy client inputs to a correct optimization formulation.

## Test Progression

### v1: Mild (aircraft_v1/) — PASS (Test 9)
- Clean CSV + separate email with demand info
- Abbreviated column names
- Availability is per-type (must deduplicate from CSV rows)
- Demand not in CSV — must extract from email text

### v2: Medium (aircraft_v2/)
- Two CSVs with inconsistent column names (`aircraft` vs `ac_type`) — must join
- Missing value in route_ops (E195 cost on GRU-REC) — must extract from email
- Irrelevant rows (B737 in maintenance) — must filter by status
- Irrelevant columns (home_base, weekly_freq) — must ignore
- Demand buried in a multi-message forwarded email thread
- Same underlying problem, same expected optimal = 700

### v3: Hard (aircraft_v3/)
- 3 CSVs from different departments (fleet master, Q1 financials, commercial targets)
- Cost split across 3 columns (fuel + crew + maint) — must aggregate
- 3 months of data — must filter to March only (per Ana's email)
- All costs in BRL (not USD) — must NOT convert
- E195 qty=2 but 1 grounded (notes column + email confirmation) — effective=1
- Demand in monthly terms (3000/4500 pax) — must convert to daily (÷30)
- Load factor targets are explicitly NOT constraints (Ricardo says so)
- Ambiguous E195 range restriction (mentioned but no formal decision) — trap
- Irrelevant rows (B737 maintenance, GIG-based A320)
- No explicit "minimize" or "assignment" language — vague operational description
- Expected optimal = **3060 BRL**

## Folder Structure
```
scaffolding_tests/
├── README.md
├── aircraft_v1/
│   ├── fleet_ops.csv          ← single client data export
│   ├── client_email.txt       ← problem description (informal)
│   └── ground_truth.md        ← expected formulation + extraction challenges
├── aircraft_v2/
│   ├── fleet_inventory.csv    ← fleet data (types, availability, status)
│   ├── route_ops.csv          ← route-level ops data (costs, capacity — one gap)
│   ├── email_thread.txt       ← forwarded email thread (3 messages, demand + missing value)
│   └── ground_truth.md        ← expected formulation + 7 extraction challenges
└── aircraft_v3/
    ├── fleet_master.csv       ← asset system (qty, status, notes with grounded unit)
    ├── route_financials_q1.csv ← Q1 accounting data (3 cost cols × 3 months × 6 routes)
    ├── commercial_targets.csv ← monthly demand + load factor targets
    ├── email_thread.txt       ← 4-message thread (cost aggregation, date filter, soft constraints)
    └── ground_truth.md        ← expected formulation + 9 extraction challenges
```
