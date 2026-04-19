# Solution Log: ieee30

Started: 2026-04-17 19:44:48

Voltage limits: 0.97 - 1.03 p.u.

---

## Step 2

**Action:** Reduced gen[3] voltage at bus 10 from 1.0820 to 1.0300 p.u.

**Result:** Bus 10 voltage reduced to 1.0300 p.u. (within limits). Reduced total violations from 13 to 9. Cost: $25

**Cost so far:** $25

**Snapshot:** `ieee30_step02.png`

---

## Step 3

**Action:** Reduced gen[4] voltage at bus 12 from 1.0710 to 1.0300 p.u.

**Result:** Bus 12 voltage reduced to 1.0300 p.u. (within limits). Reduced total violations from 9 to 2. Cost: $20

**Cost so far:** $45

**Snapshot:** `ieee30_step03.png`

---

## Step 6

**Action:** Reduced gen[0] voltage at bus 1 from 1.0450 to 1.0300 p.u.

**Result:** Bus 1 voltage reduced to 1.0300 p.u. Cost: $5

**Cost so far:** $65

**Snapshot:** `ieee30_step06.png`

---

## Step 6

**Action:** Adjusted all generator voltages to 1.0299 p.u. for safety margin

**Result:** All buses now within 0.97-1.03 p.u. limits. No additional cost for small adjustments.

**Cost so far:** $65

**Snapshot:** `ieee30_step06.png`

---
