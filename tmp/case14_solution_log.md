# Solution Log: case14

Started: 2026-04-17 19:35:10

---

## Step 2

**Action:** Lowered slack bus 0 (ext_grid[0]) from 1.060 to 1.050

**Result:** Bus 0 voltage now within limits (1.050 pu). Violations reduced from 9 to 8.

**Snapshot:** `case14_step02.png`

---

## Step 3

**Action:** Lowered gen[2] at bus 5 from 1.070 to 1.050

**Result:** Bus 5 voltage now within limits (1.050 pu). Many downstream buses improved. Violations reduced from 8 to 2.

**Snapshot:** `case14_step03.png`

---

## Step 4

**Action:** Lowered gen[3] at bus 7 from 1.090 to 1.050

**Result:** Bus 7 voltage now within limits (1.050 pu). Bus 6 also within limits (1.0374 pu). All 14 buses now within 0.95-1.05 p.u. limits.

**Snapshot:** `case14_step04.png`

---
