# web_app.py — Browser-Based Power Flow Solver

A Flask web application with an interactive network diagram
for solving power flow problems visually.

## What it does

- Serves a single-page app at `http://localhost:5050`
- Renders the IEEE 14-bus network on an HTML canvas with:
  - Buses colored by voltage (green/blue/red)
  - Lines colored and sized by loading percentage
  - MW flow direction arrows
  - Bus kV levels, generation, and load annotations
- Sidebar controls for real-time adjustments:
  - Generator voltage setpoints
  - Transformer tap positions
  - Shunt compensation (add/remove)
  - Load scaling slider (increase for a challenge)
- All changes re-run power flow instantly and update the plot

## How to run

```bash
source .venv/bin/activate
python web_app.py
```

Then open http://localhost:5050 in your browser.

## Dependencies

Requires `flask` and `plotly` (in addition to base project deps):

```bash
pip install flask plotly
```
