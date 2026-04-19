# interactive_pf.py — Terminal Power Flow Solver

A command-line interactive tool for manually adjusting power
system parameters and observing the effects on the IEEE 14-bus
network.

## What it does

- Loads the IEEE 14-bus network and runs power flow
- Displays a matplotlib plot with buses colored by voltage
  and lines colored by loading
- Provides a REPL where you type commands to adjust the system

## Commands

| Command | Description |
|---------|-------------|
| `gen <idx> <vm_pu>` | Set generator voltage (use `ext` for slack) |
| `shunt <bus> <q_mvar>` | Add capacitive (negative) or inductive shunt |
| `rmshunt <idx>` | Remove a shunt by index |
| `tap <trafo_idx> <tap_pos>` | Adjust transformer tap position |
| `run` | Re-run power flow and update the plot |
| `status` | Print voltage and loading summary |
| `show` | List all generators, trafos, and shunts |
| `reset` | Reset network to original state |
| `quit` | Exit |

## How to run

```bash
source .venv/bin/activate
python interactive_pf.py
```

A matplotlib window will open with the network diagram.
Use the terminal prompt to make changes, then type `run`
to see the updated results.
