"""Explore the IEEE 14-bus system and generate a network diagram."""

import pandapower as pp
import pandapower.topology as top
from pandapower import networks as pn
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path
import networkx as nx

output_dir = Path(__file__).parent / "output"
output_dir.mkdir(exist_ok=True)

# Load and solve
net = pn.case14()
pp.runpp(net)

# Print system overview
print("=== IEEE 14-Bus System Overview ===\n")
print(f"Buses:        {len(net.bus)}")
print(f"Lines:        {len(net.line)}")
print(f"Transformers: {len(net.trafo)}")
print(f"Generators:   {len(net.gen) + len(net.ext_grid)}")
print(f"Loads:        {len(net.load)}")
print(f"Shunts:       {len(net.shunt)}")

print("\n--- Bus Data ---")
print(net.bus[["name", "vn_kv"]].to_string())

print("\n--- Bus Voltages (after power flow) ---")
for bus in net.bus.index:
    v = net.res_bus.vm_pu.at[bus]
    angle = net.res_bus.va_degree.at[bus]
    flag = " *** >1.05" if v > 1.05 else ""
    print(f"  Bus {bus:2d}: {v:.4f} pu, {angle:7.2f}°{flag}")

print("\n--- Generator Setpoints ---")
print("  Ext grid (slack):")
for i in net.ext_grid.index:
    print(
        f"    Bus {net.ext_grid.at[i, 'bus']}: "
        f"Vm={net.ext_grid.at[i, 'vm_pu']:.2f} pu, "
        f"P={net.res_ext_grid.at[i, 'p_mw']:.2f} MW"
    )
print("  Generators:")
for i in net.gen.index:
    print(
        f"    Bus {net.gen.at[i, 'bus']}: "
        f"Vm={net.gen.at[i, 'vm_pu']:.2f} pu, "
        f"P={net.gen.at[i, 'p_mw']:.2f} MW"
    )

print("\n--- Loads ---")
for i in net.load.index:
    print(
        f"  Bus {net.load.at[i, 'bus']:2d}: "
        f"P={net.load.at[i, 'p_mw']:6.2f} MW, "
        f"Q={net.load.at[i, 'q_mvar']:6.2f} Mvar"
    )

print("\n--- Line Loading ---")
for i in net.line.index:
    fb = net.line.at[i, "from_bus"]
    tb = net.line.at[i, "to_bus"]
    ld = net.res_line.at[i, "loading_percent"]
    print(f"  Line {i:2d} ({fb:2d}->{tb:2d}): {ld:.2f}%")

# Generate network diagram using networkx layout
graph = top.create_nxgraph(net, respect_switches=True)
pos = nx.kamada_kawai_layout(graph)

fig, ax = plt.subplots(figsize=(14, 10))

# Color buses by type
gen_buses = set(net.ext_grid.bus.tolist() + net.gen.bus.tolist())
load_buses = set(net.load.bus.tolist())
colors = []
for bus in net.bus.index:
    if bus in gen_buses:
        colors.append("red")
    elif bus in load_buses:
        colors.append("steelblue")
    else:
        colors.append("grey")

nx.draw_networkx_edges(graph, pos, ax=ax, edge_color="grey", width=1.5, alpha=0.6)
nx.draw_networkx_nodes(graph, pos, ax=ax, node_color=colors, node_size=400)

# Label each bus with voltage
labels = {
    bus: f"Bus {bus}\n{net.res_bus.vm_pu.at[bus]:.3f} pu" for bus in net.bus.index
}
nx.draw_networkx_labels(graph, pos, labels, ax=ax, font_size=7)

# Legend
legend_items = [
    Line2D(
        [0],
        [0],
        marker="o",
        color="w",
        markerfacecolor="red",
        markersize=10,
        label="Generator",
    ),
    Line2D(
        [0],
        [0],
        marker="o",
        color="w",
        markerfacecolor="steelblue",
        markersize=10,
        label="Load",
    ),
    Line2D(
        [0],
        [0],
        marker="o",
        color="w",
        markerfacecolor="grey",
        markersize=10,
        label="Other",
    ),
]
ax.legend(handles=legend_items, loc="upper left")

ax.set_title("IEEE 14-Bus System — Voltage Profile", fontsize=14)
ax.set_axis_off()

img_path = output_dir / "case14_network.png"
plt.savefig(str(img_path), dpi=150, bbox_inches="tight")
plt.close()
print(f"\nNetwork diagram saved to: {img_path.absolute()}")
