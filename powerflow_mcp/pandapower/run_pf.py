from mcp.server.fastmcp import FastMCP, Context
from pandapower import networks as pn
import pandapower as pp
from pathlib import Path
from pandapower import to_pickle
import matplotlib.pyplot as plt
from datetime import datetime
import warnings
import logging

warnings.filterwarnings("ignore")
logging.getLogger("mcp.server").setLevel(logging.ERROR)
logging.getLogger("matplotlib").setLevel(logging.ERROR)

tmep_folder = Path(__file__).parent / "tmp"
tmep_folder.mkdir(exist_ok=True, parents=True)

mcp = FastMCP("run_pandapower_pf")

# Step counter per network for snapshot naming
_step_counters: dict[str, int] = {}
# Cost tracker per network
_cost_trackers: dict[str, float] = {}

# Cost per action type
COSTS = {
    "gen_voltage_change_per_0.01pu": 5.0,
    "shunt_per_mvar": 2.0,
    "tap_change_per_step": 10.0,
}


def _create_challenge_ieee30():
    """Create a harder ieee30 with both over and undervoltage problems."""
    net = pn.case_ieee30()
    # Increase loads at remote buses to create undervoltage pockets
    for idx in net.load.index:
        bus = net.load.at[idx, "bus"]
        if bus in [6, 7, 17, 18, 19, 25, 29]:
            net.load.at[idx, "p_mw"] *= 2.0
            net.load.at[idx, "q_mvar"] *= 2.5
    return net


NETWORKS = {
    "case9": pn.case9,
    "case14": pn.case14,
    "case30": pn.case30,
    "ieee30": pn.case_ieee30,
    "ieee30_challenge": _create_challenge_ieee30,
    "cigre_mv": pn.create_cigre_network_mv,
    "case118": pn.case118,
    "case300": pn.case300,
    "case1888": pn.case1888rte,
    "case2848": pn.case2848rte,
    "case3120": pn.case3120sp,
    "case6470": pn.case6470rte,
    "case6515": pn.case6515rte,
    "case9241": pn.case9241pegase,
}


def _get_step(network: str) -> int:
    step = _step_counters.get(network, 0)
    _step_counters[network] = step + 1
    return step


def _add_cost(network: str, amount: float) -> float:
    _cost_trackers[network] = _cost_trackers.get(network, 0) + amount
    return _cost_trackers[network]


def _save_voltage_plot(
    net,
    network: str,
    step: int,
    label: str,
    v_min: float = 0.97,
    v_max: float = 1.03,
) -> Path:
    """Save a voltage bar chart snapshot for a given step."""
    vm = net.res_bus.vm_pu
    buses = net.bus.index.tolist()

    fig, ax = plt.subplots(figsize=(14, 5))
    colors = ["red" if v > v_max or v < v_min else "steelblue" for v in vm]
    ax.bar([str(b) for b in buses], vm, color=colors)
    ax.axhline(
        y=v_max,
        color="red",
        linestyle="--",
        linewidth=0.8,
        label=f"{v_max} limit",
    )
    ax.axhline(
        y=v_min,
        color="red",
        linestyle="--",
        linewidth=0.8,
        label=f"{v_min} limit",
    )
    ax.set_xlabel("Bus")
    ax.set_ylabel("Voltage (p.u.)")
    cost = _cost_trackers.get(network, 0)
    ax.set_title(f"Step {step}: {label}  |  Cost: ${cost:.0f}")
    ax.set_ylim(0.92, 1.10)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plot_path = tmep_folder / f"{network}_step{step:02d}.png"
    plt.savefig(str(plot_path), dpi=120, bbox_inches="tight")
    plt.close(fig)
    return plot_path


def _load_net(network: str):
    return pp.from_pickle(open(str((tmep_folder / f"{network}.p").absolute()), "rb"))


def _save_net(net, network: str):
    to_pickle(net, str((tmep_folder / f"{network}.p").absolute()))


# ── Core tools ──────────────────────────────────────────


@mcp.tool()
async def get_available_networks() -> list[str]:
    """Get list of available pandapower network names."""
    return list(NETWORKS.keys())


@mcp.tool()
async def run_pf(network: str, ctx: Context) -> str:
    """
    Load a fresh network, run power flow, and save it.
    Resets step counter and cost to zero.

    Args:
        network: Name of pandapower network.
    """
    try:
        net = NETWORKS[network]()
    except Exception:
        return "Network not found."

    await ctx.info(f"Running powerflow on {network}...")
    pp.runpp(net)
    _save_net(net, network)

    _step_counters[network] = 0
    _cost_trackers[network] = 0
    step = _get_step(network)
    plot_path = _save_voltage_plot(
        net, network, step, "Initial network (before changes)"
    )

    return (
        f"Powerflow completed. Network saved.\n"
        f"Initial snapshot: {plot_path.absolute()}\n"
        f"Cost so far: $0"
    )


@mcp.tool()
async def reset_network(network: str, ctx: Context) -> str:
    """
    Reset the network to its original state and re-run power flow.
    Use this if your changes made things worse and you want to start over.
    Preserves the solution log so you can learn from the failed attempt.
    Resets cost to zero.

    Args:
        network: Name of pandapower network.
    """
    try:
        net = NETWORKS[network]()
    except Exception:
        return "Network not found."

    await ctx.info(f"Resetting {network} to original state...")
    pp.runpp(net)
    _save_net(net, network)

    _step_counters[network] = 0
    _cost_trackers[network] = 0
    step = _get_step(network)
    plot_path = _save_voltage_plot(net, network, step, "RESET — back to original")

    # Log the reset
    log_path = tmep_folder / f"{network}_solution_log.md"
    if log_path.exists():
        with open(log_path, "a") as f:
            f.write(
                f"\n## RESET\n\n"
                f"Network reset to original state at "
                f"{datetime.now().strftime('%H:%M:%S')}.\n"
                f"Starting fresh approach.\n\n---\n\n"
            )

    return (
        f"Network reset to original state. Power flow solved.\n"
        f"Snapshot: {plot_path.absolute()}\n"
        f"Cost reset to $0"
    )


@mcp.tool()
async def rerun_pf(network: str, step_label: str = "") -> str:
    """
    Re-run power flow after making changes.
    Saves a voltage snapshot for this step.

    Args:
        network: Name of pandapower network.
        step_label: Short description of what was changed.
    """
    net = _load_net(network)

    try:
        pp.runpp(net)
    except Exception as e:
        return f"Power flow FAILED to converge: {e}"

    _save_net(net, network)

    step = _get_step(network)
    label = step_label or f"After adjustment (step {step})"
    plot_path = _save_voltage_plot(net, network, step, label)
    cost = _cost_trackers.get(network, 0)

    return (
        f"Power flow converged.\n"
        f"Snapshot: {plot_path.absolute()}\n"
        f"Total cost so far: ${cost:.0f}\n"
        f"Call check_violations to see results."
    )


# ── Remedial action tools ───────────────────────────────


@mcp.tool()
async def set_gen_voltage(network: str, gen_type: str, index: int, vm_pu: float) -> str:
    """
    Adjust a generator's voltage setpoint.
    Cost: $5 per 0.01 p.u. change.

    Args:
        network: Name of pandapower network.
        gen_type: "ext_grid" for slack bus or "gen" for PV generators.
        index: Index of the generator or ext_grid to modify.
        vm_pu: New voltage setpoint in p.u. (range 0.95-1.10).
    """
    if vm_pu < 0.95 or vm_pu > 1.10:
        return "Error: vm_pu must be between 0.95 and 1.10."
    if gen_type not in ("ext_grid", "gen"):
        return "Error: gen_type must be 'ext_grid' or 'gen'."

    net = _load_net(network)

    if gen_type == "ext_grid":
        if index not in net.ext_grid.index:
            return f"Error: ext_grid index {index} not found."
        old = net.ext_grid.at[index, "vm_pu"]
        net.ext_grid.at[index, "vm_pu"] = vm_pu
        bus = net.ext_grid.at[index, "bus"]
    else:
        if index not in net.gen.index:
            return f"Error: gen index {index} not found."
        old = net.gen.at[index, "vm_pu"]
        net.gen.at[index, "vm_pu"] = vm_pu
        bus = net.gen.at[index, "bus"]

    _save_net(net, network)

    change = abs(vm_pu - old)
    cost = round(change / 0.01) * COSTS["gen_voltage_change_per_0.01pu"]
    total = _add_cost(network, cost)

    return (
        f"Updated {gen_type}[{index}] on bus {bus}: "
        f"vm_pu {old:.4f} -> {vm_pu:.4f}.\n"
        f"Action cost: ${cost:.0f} | Total cost: ${total:.0f}"
    )


@mcp.tool()
async def add_shunt(network: str, bus: int, q_mvar: float) -> str:
    """
    Add a shunt compensator at a bus.
    Positive q_mvar = reactor (absorbs reactive power, lowers voltage).
    Negative q_mvar = capacitor (injects reactive power, raises voltage).
    Cost: $2 per Mvar.

    Args:
        network: Name of pandapower network.
        bus: Bus index to add the shunt to.
        q_mvar: Reactive power in Mvar. Positive=reactor, negative=capacitor.
    """
    if abs(q_mvar) > 50:
        return "Error: q_mvar must be between -50 and 50."

    net = _load_net(network)

    if bus not in net.bus.index:
        return f"Error: bus {bus} not found."

    pp.create_shunt(net, bus=bus, q_mvar=q_mvar, p_mw=0)
    _save_net(net, network)

    cost = abs(q_mvar) * COSTS["shunt_per_mvar"]
    total = _add_cost(network, cost)
    kind = "reactor" if q_mvar > 0 else "capacitor"

    return (
        f"Added {kind} at bus {bus}: q_mvar={q_mvar:.1f}.\n"
        f"Action cost: ${cost:.0f} | Total cost: ${total:.0f}"
    )


@mcp.tool()
async def adjust_trafo_tap(network: str, trafo_index: int, tap_pos: int) -> str:
    """
    Adjust a transformer's tap position.
    Higher tap = lower voltage on LV side. Lower tap = higher voltage on LV side.
    Cost: $10 per tap step change.

    Args:
        network: Name of pandapower network.
        trafo_index: Index of the transformer.
        tap_pos: New tap position (integer).
    """
    net = _load_net(network)

    if trafo_index not in net.trafo.index:
        return f"Error: trafo index {trafo_index} not found."

    if "tap_pos" not in net.trafo.columns:
        return "Error: this network's transformers don't have tap changers."

    old = net.trafo.at[trafo_index, "tap_pos"]
    if str(old) == "nan":
        return (
            f"Error: trafo[{trafo_index}] does not have a tap changer "
            f"(tap_pos is NaN). Only trafos with existing tap changers "
            f"can be adjusted."
        )

    net.trafo.at[trafo_index, "tap_pos"] = tap_pos
    _save_net(net, network)

    steps_changed = abs(tap_pos - int(old))
    cost = steps_changed * COSTS["tap_change_per_step"]
    total = _add_cost(network, cost)

    hv = net.trafo.at[trafo_index, "hv_bus"]
    lv = net.trafo.at[trafo_index, "lv_bus"]

    return (
        f"Updated trafo[{trafo_index}] (bus {hv}->{lv}): "
        f"tap {int(old)} -> {tap_pos}.\n"
        f"Action cost: ${cost:.0f} | Total cost: ${total:.0f}"
    )


# ── Analysis tools ──────────────────────────────────────


@mcp.tool()
async def check_violations(
    network: str, v_min: float = 0.97, v_max: float = 1.03
) -> str:
    """
    Check for voltage violations on a solved network.
    Default limits are the tighter 0.97-1.03 p.u. band.

    Args:
        network: Name of pandapower network.
        v_min: Minimum acceptable voltage in p.u. (default 0.97).
        v_max: Maximum acceptable voltage in p.u. (default 1.03).
    """
    net = _load_net(network)
    vm = net.res_bus.vm_pu
    cost = _cost_trackers.get(network, 0)

    lines = [f"=== Voltage Check ({v_min}-{v_max} p.u.) | Cost: ${cost:.0f} ===\n"]

    violations = 0
    for bus in net.bus.index:
        v = vm.at[bus]
        status = ""
        if v < v_min:
            status = " *** UNDERVOLTAGE"
            violations += 1
        elif v > v_max:
            status = " *** OVERVOLTAGE"
            violations += 1
        lines.append(f"  Bus {bus:2d}: {v:.4f} pu{status}")

    lines.append(f"\nViolations: {violations} / {len(net.bus)} buses")
    if violations == 0:
        lines.append(f"ALL BUSES WITHIN LIMITS! Final cost: ${cost:.0f}")
    else:
        lines.append("Available actions: set_gen_voltage, add_shunt, adjust_trafo_tap")

    return "\n".join(lines)


@mcp.tool()
async def get_generators(network: str) -> str:
    """
    Get all generator voltage setpoints and reactive power output.

    Args:
        network: Name of pandapower network.
    """
    net = _load_net(network)
    lines = [f"=== Generators for {network} ===\n"]

    lines.append("-- Slack Bus (ext_grid) --")
    for i in net.ext_grid.index:
        s = (
            f"  ext_grid[{i}] bus={net.ext_grid.at[i, 'bus']},"
            f" vm_pu={net.ext_grid.at[i, 'vm_pu']:.4f}"
        )
        if not net.res_ext_grid.empty:
            s += (
                f" | P={net.res_ext_grid.at[i, 'p_mw']:.2f} MW,"
                f" Q={net.res_ext_grid.at[i, 'q_mvar']:.2f} Mvar"
            )
        lines.append(s)

    lines.append("\n-- Generators (PV buses) --")
    for i in net.gen.index:
        s = (
            f"  gen[{i}] bus={net.gen.at[i, 'bus']},"
            f" vm_pu={net.gen.at[i, 'vm_pu']:.4f},"
            f" p_mw={net.gen.at[i, 'p_mw']:.2f}"
        )
        if not net.res_gen.empty:
            s += f" | Q={net.res_gen.at[i, 'q_mvar']:.2f} Mvar"
        lines.append(s)

    return "\n".join(lines)


@mcp.tool()
async def get_transformers(network: str) -> str:
    """
    Get all transformer details including tap positions.

    Args:
        network: Name of pandapower network.
    """
    net = _load_net(network)

    if net.trafo.empty:
        return f"No transformers in {network}."

    lines = [f"=== Transformers for {network} ===\n"]
    for i in net.trafo.index:
        tap = net.trafo.at[i, "tap_pos"] if "tap_pos" in net.trafo.columns else "N/A"
        has_tap = str(tap) != "nan"
        s = (
            f"  trafo[{i}] hv_bus={net.trafo.at[i, 'hv_bus']}"
            f" -> lv_bus={net.trafo.at[i, 'lv_bus']},"
            f" sn_mva={net.trafo.at[i, 'sn_mva']:.1f},"
            f" tap_pos={tap}"
            f" {'(adjustable)' if has_tap else '(no tap changer)'}"
        )
        if not net.res_trafo.empty:
            s += f" | loading={net.res_trafo.at[i, 'loading_percent']:.2f}%"
        lines.append(s)

    return "\n".join(lines)


@mcp.tool()
async def get_shunts(network: str) -> str:
    """
    Get all shunt compensators in the network.

    Args:
        network: Name of pandapower network.
    """
    net = _load_net(network)

    if net.shunt.empty:
        return f"No shunts in {network}."

    lines = [f"=== Shunts for {network} ===\n"]
    for i in net.shunt.index:
        q = net.shunt.at[i, "q_mvar"]
        kind = "reactor" if q > 0 else "capacitor"
        lines.append(
            f"  shunt[{i}] bus={net.shunt.at[i, 'bus']}, q_mvar={q:.2f} ({kind})"
        )

    return "\n".join(lines)


@mcp.tool()
async def describe_network(network: str) -> str:
    """
    Full network description with all components and results.

    Args:
        network: Name of pandapower network.
    """
    net = _load_net(network)
    sections = [f"=== Network: {network} ===\n"]

    sections.append("-- Buses --")
    for i in net.bus.index:
        s = f"  Bus {i}: vn_kv={net.bus.at[i, 'vn_kv']}"
        if not net.res_bus.empty:
            s += (
                f" | vm={net.res_bus.at[i, 'vm_pu']:.4f} pu,"
                f" va={net.res_bus.at[i, 'va_degree']:.2f}°"
            )
        sections.append(s)

    sections.append("\n-- Slack Bus (ext_grid) --")
    for i in net.ext_grid.index:
        s = (
            f"  idx={i}, bus={net.ext_grid.at[i, 'bus']},"
            f" vm_pu={net.ext_grid.at[i, 'vm_pu']:.4f}"
        )
        if not net.res_ext_grid.empty:
            s += (
                f" | P={net.res_ext_grid.at[i, 'p_mw']:.2f} MW,"
                f" Q={net.res_ext_grid.at[i, 'q_mvar']:.2f} Mvar"
            )
        sections.append(s)

    if not net.gen.empty:
        sections.append("\n-- Generators --")
        for i in net.gen.index:
            s = (
                f"  idx={i}, bus={net.gen.at[i, 'bus']},"
                f" vm_pu={net.gen.at[i, 'vm_pu']:.4f},"
                f" p_mw={net.gen.at[i, 'p_mw']:.2f}"
            )
            if not net.res_gen.empty:
                s += f" | Q={net.res_gen.at[i, 'q_mvar']:.2f} Mvar"
            sections.append(s)

    if not net.load.empty:
        sections.append("\n-- Loads --")
        for i in net.load.index:
            sections.append(
                f"  idx={i}, bus={net.load.at[i, 'bus']},"
                f" p_mw={net.load.at[i, 'p_mw']:.2f},"
                f" q_mvar={net.load.at[i, 'q_mvar']:.2f}"
            )

    if not net.line.empty:
        sections.append("\n-- Lines --")
        for i in net.line.index:
            s = (
                f"  idx={i},"
                f" {net.line.at[i, 'from_bus']}->"
                f"{net.line.at[i, 'to_bus']},"
                f" length={net.line.at[i, 'length_km']:.2f} km"
            )
            if not net.res_line.empty:
                s += f" | loading={net.res_line.at[i, 'loading_percent']:.2f}%"
            sections.append(s)

    if not net.trafo.empty:
        sections.append("\n-- Transformers --")
        for i in net.trafo.index:
            tap = (
                net.trafo.at[i, "tap_pos"] if "tap_pos" in net.trafo.columns else "N/A"
            )
            s = (
                f"  idx={i},"
                f" hv={net.trafo.at[i, 'hv_bus']}->"
                f"lv={net.trafo.at[i, 'lv_bus']},"
                f" sn_mva={net.trafo.at[i, 'sn_mva']:.1f},"
                f" tap={tap}"
            )
            if not net.res_trafo.empty:
                s += f" | loading={net.res_trafo.at[i, 'loading_percent']:.2f}%"
            sections.append(s)

    if not net.shunt.empty:
        sections.append("\n-- Shunts --")
        for i in net.shunt.index:
            sections.append(
                f"  idx={i}, bus={net.shunt.at[i, 'bus']},"
                f" q_mvar={net.shunt.at[i, 'q_mvar']:.2f}"
            )

    return "\n".join(sections)


@mcp.tool()
async def get_cost_summary(network: str) -> str:
    """
    Get the current cost breakdown and pricing info.

    Args:
        network: Name of pandapower network.
    """
    cost = _cost_trackers.get(network, 0)
    return (
        f"=== Cost Summary for {network} ===\n\n"
        f"Total cost: ${cost:.0f}\n\n"
        f"Pricing:\n"
        f"  Generator voltage change: "
        f"${COSTS['gen_voltage_change_per_0.01pu']:.0f} per 0.01 p.u.\n"
        f"  Shunt compensator: "
        f"${COSTS['shunt_per_mvar']:.0f} per Mvar\n"
        f"  Transformer tap change: "
        f"${COSTS['tap_change_per_step']:.0f} per tap step"
    )


# ── Logging tools ───────────────────────────────────────


@mcp.tool()
async def log_action(network: str, action: str, result: str) -> str:
    """
    Log an action to the solution markdown file.

    Args:
        network: Name of pandapower network.
        action: What was done.
        result: What happened.
    """
    log_path = tmep_folder / f"{network}_solution_log.md"
    step = _step_counters.get(network, 0)
    cost = _cost_trackers.get(network, 0)

    if not log_path.exists():
        header = (
            f"# Solution Log: {network}\n\n"
            f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Voltage limits: 0.97 - 1.03 p.u.\n\n"
            f"---\n\n"
        )
        log_path.write_text(header)

    entry = (
        f"## Step {step}\n\n"
        f"**Action:** {action}\n\n"
        f"**Result:** {result}\n\n"
        f"**Cost so far:** ${cost:.0f}\n\n"
        f"**Snapshot:** `{network}_step{step:02d}.png`\n\n"
        f"---\n\n"
    )

    with open(log_path, "a") as f:
        f.write(entry)

    return f"Logged step {step} to {log_path.absolute()}"


@mcp.tool()
async def read_solution_log(network: str) -> str:
    """
    Read the solution log from previous attempts.
    Use this at the start to learn from past tries.

    Args:
        network: Name of pandapower network.
    """
    log_path = tmep_folder / f"{network}_solution_log.md"

    if not log_path.exists():
        return (
            f"No solution log found for {network}. Fresh attempt.\n"
            f"Tip: voltage limits are 0.97-1.03 p.u. (tight band).\n"
            f"Available tools: set_gen_voltage, add_shunt,"
            f" adjust_trafo_tap.\n"
            f"Each action has a cost — try to minimize total cost."
        )

    return log_path.read_text()


if __name__ == "__main__":
    mcp.run(transport="stdio")
