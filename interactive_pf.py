"""
Interactive power flow solver.

Lets you manually adjust generator voltages, shunt compensation, and
transformer taps on the IEEE 14-bus network, then re-run power flow
and see the results on a geographic network plot.
"""

import pandapower as pp
import pandapower.networks as pn
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx


def create_network():
    """Load IEEE 14-bus and generate geographic layout."""
    net = pn.case14()
    pp.runpp(net)

    # Build networkx graph for layout
    G = nx.Graph()
    for _, row in net.line.iterrows():
        G.add_edge(int(row["from_bus"]), int(row["to_bus"]))
    for _, row in net.trafo.iterrows():
        G.add_edge(int(row["hv_bus"]), int(row["lv_bus"]))

    # Kamada-Kawai gives more even spacing than spring
    pos = nx.kamada_kawai_layout(G)
    return net, pos


def plot_network(net, pos, title="IEEE 14-Bus Power Flow"):
    """Plot the network with voltage coloring and line loading."""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))

    # Draw lines with loading colors
    for _, row in net.line.iterrows():
        fb, tb = int(row["from_bus"]), int(row["to_bus"])
        if fb in pos and tb in pos:
            x = [pos[fb][0], pos[tb][0]]
            y = [pos[fb][1], pos[tb][1]]
            # Color by loading
            loading = (
                net.res_line.loc[_, "loading_percent"] if _ in net.res_line.index else 0
            )
            color = "green" if loading < 50 else "orange" if loading < 80 else "red"
            lw = 1.5 + loading / 50
            ax.plot(x, y, color=color, linewidth=lw, alpha=0.7, zorder=1)
            # Loading label
            mx, my = (x[0] + x[1]) / 2, (y[0] + y[1]) / 2
            ax.text(mx, my, f"{loading:.0f}%", fontsize=7, ha="center", color=color)

    # Draw transformers as dashed
    for _, row in net.trafo.iterrows():
        hv, lv = int(row["hv_bus"]), int(row["lv_bus"])
        if hv in pos and lv in pos:
            x = [pos[hv][0], pos[lv][0]]
            y = [pos[hv][1], pos[lv][1]]
            loading = (
                net.res_trafo.loc[_, "loading_percent"]
                if _ in net.res_trafo.index
                else 0
            )
            color = "green" if loading < 50 else "orange" if loading < 80 else "red"
            ax.plot(x, y, color=color, linewidth=2, linestyle="--", alpha=0.7, zorder=1)

    # Draw buses with voltage coloring
    for bus_idx in net.bus.index:
        if bus_idx not in pos:
            continue
        vm = net.res_bus.loc[bus_idx, "vm_pu"]
        # Color: blue=low, green=good, red=high
        if vm < 0.95:
            color = "royalblue"
        elif vm > 1.05:
            color = "crimson"
        else:
            color = "limegreen"

        is_gen = (
            bus_idx in net.gen["bus"].values or bus_idx in net.ext_grid["bus"].values
        )
        marker = "s" if is_gen else "o"
        size = 200 if is_gen else 120

        ax.scatter(
            pos[bus_idx][0],
            pos[bus_idx][1],
            c=color,
            s=size,
            marker=marker,
            zorder=3,
            edgecolors="black",
            linewidths=0.8,
        )
        ax.annotate(
            f"Bus {bus_idx}\n{vm:.3f} pu",
            pos[bus_idx],
            fontsize=7,
            ha="center",
            va="bottom",
            xytext=(0, 10),
            textcoords="offset points",
        )

    # Legend
    legend_elements = [
        mpatches.Patch(color="limegreen", label="0.95 ≤ V ≤ 1.05 pu"),
        mpatches.Patch(color="royalblue", label="V < 0.95 pu"),
        mpatches.Patch(color="crimson", label="V > 1.05 pu"),
        plt.Line2D([0], [0], color="green", lw=2, label="Loading < 50%"),
        plt.Line2D([0], [0], color="orange", lw=2, label="Loading 50-80%"),
        plt.Line2D([0], [0], color="red", lw=2, label="Loading > 80%"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=8)
    ax.set_title(title)
    ax.axis("off")
    plt.tight_layout()
    plt.show(block=False)
    plt.pause(0.1)


def print_status(net):
    """Print voltage and loading summary."""
    print("\n" + "=" * 60)
    print("VOLTAGE PROFILE")
    print("-" * 60)
    for bus_idx in net.bus.index:
        vm = net.res_bus.loc[bus_idx, "vm_pu"]
        flag = " ⚠️" if vm < 0.95 or vm > 1.05 else " ✓"
        print(f"  Bus {bus_idx:3d}: {vm:.4f} pu{flag}")

    print("\nLINE LOADING")
    print("-" * 60)
    for idx in net.res_line.index:
        loading = net.res_line.loc[idx, "loading_percent"]
        flag = " ⚠️" if loading > 80 else ""
        fb = net.line.loc[idx, "from_bus"]
        tb = net.line.loc[idx, "to_bus"]
        print(f"  Line {idx:3d} ({fb}->{tb}): {loading:.1f}%{flag}")

    violations = (net.res_bus["vm_pu"] < 0.95).sum() + (
        net.res_bus["vm_pu"] > 1.05
    ).sum()
    overloads = (net.res_line["loading_percent"] > 100).sum()
    print(f"\nVoltage violations: {violations} | Line overloads: {overloads}")
    print("=" * 60)


def print_generators(net):
    """Show current generator settings."""
    print("\nGENERATORS")
    print("-" * 40)
    for idx, row in net.ext_grid.iterrows():
        print(f"  [ext_grid {idx}] Bus {row['bus']}: vm_pu={row['vm_pu']:.4f}")
    for idx, row in net.gen.iterrows():
        print(
            f"  [gen {idx}] Bus {row['bus']}:"
            f" vm_pu={row['vm_pu']:.4f},"
            f" p_mw={row['p_mw']:.1f}"
        )


def print_trafos(net):
    """Show transformer settings."""
    print("\nTRANSFORMERS")
    print("-" * 40)
    for idx, row in net.trafo.iterrows():
        tap = row.get("tap_pos", 0)
        print(f"  [trafo {idx}] {row['hv_bus']}->{row['lv_bus']}: tap_pos={tap}")


def print_shunts(net):
    """Show shunt compensation."""
    print("\nSHUNTS")
    print("-" * 40)
    if len(net.shunt) == 0:
        print("  (none)")
    for idx, row in net.shunt.iterrows():
        print(f"  [shunt {idx}] Bus {row['bus']}: q_mvar={row['q_mvar']:.2f}")


def run_and_show(net, pos):
    """Run power flow and display results."""
    try:
        pp.runpp(net)
        print_status(net)
        plot_network(net, pos)
    except Exception as e:
        print(f"Power flow failed: {e}")


def print_help():
    print("""
COMMANDS:
  gen <idx> <vm_pu>         - Set generator voltage (use 'ext' for ext_grid 0)
  shunt <bus> <q_mvar>      - Add/modify shunt at bus (negative = capacitive)
  rmshunt <idx>             - Remove shunt by index
  tap <trafo_idx> <tap_pos> - Set transformer tap position
  run                       - Re-run power flow and update plot
  status                    - Print current results
  show                      - Show generators, trafos, shunts
  reset                     - Reset network to original
  help                      - Show this help
  quit                      - Exit
""")


def main():
    print("=" * 60)
    print("  INTERACTIVE POWER FLOW SOLVER - IEEE 14-Bus")
    print("=" * 60)
    print("\nAdjust generator voltages, shunts, and transformer taps")
    print("to solve voltage violations and reduce line loading.")
    print("Type 'help' for commands.\n")

    net, pos = create_network()
    run_and_show(net, pos)

    while True:
        try:
            cmd = input("\n> ").strip().lower().split()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not cmd:
            continue

        action = cmd[0]

        if action == "quit" or action == "q":
            print("Bye!")
            break

        elif action == "help" or action == "h":
            print_help()

        elif action == "run" or action == "r":
            run_and_show(net, pos)

        elif action == "status":
            print_status(net)

        elif action == "show":
            print_generators(net)
            print_trafos(net)
            print_shunts(net)

        elif action == "reset":
            plt.close("all")
            net, pos = create_network()
            run_and_show(net, pos)
            print("Network reset.")

        elif action == "gen":
            if len(cmd) < 3:
                print("Usage: gen <idx|ext> <vm_pu>")
                continue
            try:
                vm = float(cmd[2])
                if cmd[1] == "ext":
                    net.ext_grid.at[0, "vm_pu"] = vm
                    print(f"ext_grid 0 vm_pu -> {vm}")
                else:
                    idx = int(cmd[1])
                    net.gen.at[idx, "vm_pu"] = vm
                    print(f"gen {idx} vm_pu -> {vm}")
            except (ValueError, KeyError) as e:
                print(f"Error: {e}")

        elif action == "shunt":
            if len(cmd) < 3:
                print("Usage: shunt <bus> <q_mvar>")
                continue
            try:
                bus = int(cmd[1])
                q = float(cmd[2])
                # Check if shunt already exists at this bus
                existing = net.shunt[net.shunt["bus"] == bus]
                if len(existing) > 0:
                    net.shunt.at[existing.index[0], "q_mvar"] = q
                    print(f"Updated shunt at bus {bus}: q_mvar={q}")
                else:
                    pp.create_shunt(net, bus=bus, q_mvar=q, p_mw=0)
                    print(f"Added shunt at bus {bus}: q_mvar={q}")
            except (ValueError, KeyError) as e:
                print(f"Error: {e}")

        elif action == "rmshunt":
            if len(cmd) < 2:
                print("Usage: rmshunt <idx>")
                continue
            try:
                idx = int(cmd[1])
                net.shunt.drop(idx, inplace=True)
                print(f"Removed shunt {idx}")
            except (ValueError, KeyError) as e:
                print(f"Error: {e}")

        elif action == "tap":
            if len(cmd) < 3:
                print("Usage: tap <trafo_idx> <tap_pos>")
                continue
            try:
                idx = int(cmd[1])
                tap = int(cmd[2])
                net.trafo.at[idx, "tap_pos"] = tap
                print(f"trafo {idx} tap_pos -> {tap}")
            except (ValueError, KeyError) as e:
                print(f"Error: {e}")

        else:
            print(f"Unknown command: {action}. Type 'help' for commands.")

    plt.close("all")


if __name__ == "__main__":
    main()
