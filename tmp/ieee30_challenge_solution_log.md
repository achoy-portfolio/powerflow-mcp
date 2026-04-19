# Solution Log: ieee30_challenge

Started: 2026-04-17 19:53:37

Voltage limits: 0.97 - 1.03 p.u.

---

## Step 2

**Action:** Lowered slack bus (bus 0) from 1.060 to 1.030 p.u.

**Result:** Bus 0 now within limits (1.030 p.u.). Reduced overvoltage violations from 7 to 5 buses. Bus 15 also came within limits. Cost: $15

**Cost so far:** $15

**Snapshot:** `ieee30_challenge_step02.png`

---

## Step 3

**Action:** Lowered generator at bus 10 from 1.082 to 1.030 p.u. and generator at bus 12 from 1.071 to 1.030 p.u.

**Result:** Buses 10 and 12 now within limits. Bus 8 also came within limits. However, undervoltage problems worsened significantly - now 9 buses are undervoltage. Cost: $45

**Cost so far:** $60

**Snapshot:** `ieee30_challenge_step03.png`

---

## Step 4

**Action:** Adjusted transformer 6 (bus 27->26) tap from -1 to -2

**Result:** Improved voltages in area: bus 26 now within limits (0.9896 p.u.), bus 24 improved to 0.9710 p.u., bus 23 now within limits. Reduced undervoltage violations from 9 to 6 buses. Cost: $10

**Cost so far:** $70

**Snapshot:** `ieee30_challenge_step04.png`

---

## Step 5

**Action:** Lowered generator at bus 1 from 1.045 to 1.030 p.u.

**Result:** Bus 1 now within limits. All overvoltage violations eliminated! Still have 7 undervoltage buses. Cost: $5

**Cost so far:** $75

**Snapshot:** `ieee30_challenge_step05.png`

---

## Step 6

**Action:** Adjusted transformer 4 (bus 3->11) and transformer 0 (bus 5->8) taps from -1 to -2

**Result:** Improved many undervoltage buses: 17, 18, 19, 24 now close to limits. However, created overvoltage at bus 11 (1.0382 p.u.). Still have 3 undervoltage buses (25, 28, 29). Cost: $20

**Cost so far:** $95

**Snapshot:** `ieee30_challenge_step06.png`

---


## RESET

Network reset to original state at 19:56:04.
Starting fresh approach.

---
