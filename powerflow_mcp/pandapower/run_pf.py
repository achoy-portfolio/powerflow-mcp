from mcp.server.fastmcp import FastMCP, Context
from pandapower import networks as pn
import pandapower as pp
from pathlib import Path
from pandapower import to_pickle
import pandapower.topology as top
import networkx as nx
import matplotlib.pyplot as plt

tmep_folder = Path(__file__).parent / "tmp"

tmep_folder.mkdir(exist_ok=True, parents=True)

mcp = FastMCP("run_pandapower_pf")

NETWORKS = {
    "case9": pn.case9,
    "case14": pn.case14,
    "case30": pn.case30,
    "ieee30": pn.case_ieee30,
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


@mcp.tool()
async def get_available_networks() -> list[str]:
    """
    Get list of pandapower network name from `NETWORKS` keys.
    """

    return list(NETWORKS.keys())


@mcp.tool()
async def run_pf(network: str, ctx: Context) -> str:
    """
    Run powerflow on user-selected pandapower network.

    Args:
        network: Name of pandapower network.
    """

    await ctx.info(f"Initializing network: {network}...")

    try:
        net = NETWORKS[network]()
    except Exception:
        return "Network not found."

    await ctx.info(f"Network {network} initialized successfully.")

    await ctx.info(f"Running powerflow on network {network}..")

    pp.runpp(net)

    await ctx.info(f"Powerflow on network {network} completed successfully.")

    net_path = str((tmep_folder / f"{network}.p").absolute())

    to_pickle(net, net_path)

    await ctx.info(f"Network {network} saved to {net_path}")

    return f"Powerflow completed successfully and network saved to {net_path}."


@mcp.tool()
async def analysis_pf_result(network: str) -> str:
    """
    Analysis powerflow result on user-selected pandapower network.
    Returns voltage profile, line loading, and power summary as text.
    Also saves a voltage profile plot to the tmp folder.

    Args:
        network: Name of pandapower network.
    """

    net = pp.from_pickle(open(str((tmep_folder / f"{network}.p").absolute()), "rb"))

    # --- Text results for the LLM ---
    lines = [f"=== Power Flow Results for {network} ===\n"]

    # Voltage profile
    vm = net.res_bus.vm_pu
    lines.append("-- Bus Voltage Profile (p.u.) --")
    for bus in net.bus.index:
        name = net.bus.at[bus, "name"] if "name" in net.bus.columns else f"Bus {bus}"
        lines.append(f"  {name}: {vm.at[bus]:.4f} pu")
    lines.append(f"\n  Min voltage: {vm.min():.4f} pu (bus {vm.idxmin()})")
    lines.append(f"  Max voltage: {vm.max():.4f} pu (bus {vm.idxmax()})")

    # Line loading
    if not net.res_line.empty:
        loading = net.res_line.loading_percent
        lines.append("\n-- Line Loading --")
        lines.append(f"  Max loading: {loading.max():.2f}% (line {loading.idxmax()})")
        overloaded = loading[loading > 100]
        lines.append(f"  Overloaded lines (>100%): {len(overloaded)}")

    # Power summary
    total_gen_p = net.res_ext_grid.p_mw.sum() + (
        net.res_gen.p_mw.sum() if not net.res_gen.empty else 0
    )
    total_load_p = net.res_load.p_mw.sum() if not net.res_load.empty else 0
    total_loss = total_gen_p - total_load_p
    lines.append("\n-- Power Summary --")
    lines.append(f"  Total generation: {total_gen_p:.2f} MW")
    lines.append(f"  Total load: {total_load_p:.2f} MW")
    lines.append(
        f"  Total losses: {total_loss:.2f} MW ({100 * total_loss / total_gen_p:.2f}%)"
    )

    # --- Save plot to disk ---
    slack_bus_idx = net.ext_grid.bus.iloc[0]
    graph = top.create_nxgraph(net, respect_switches=True)
    distances = nx.single_source_shortest_path_length(graph, slack_bus_idx)

    x = [distances[bus] for bus in net.bus.index]
    y = [vm.at[bus] for bus in net.bus.index]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(x, y, color="blue")
    ax.set_xlabel("Distance from Slack Bus")
    ax.set_ylabel("Bus Voltage (p.u.)")
    ax.set_title(f"Bus Voltage Profile vs Distance - {network}")
    ax.grid(True)

    plot_path = tmep_folder / f"{network}_voltage_profile.png"
    plt.savefig(str(plot_path), format="png", bbox_inches="tight")
    plt.close(fig)

    lines.append(f"\nVoltage profile plot saved to: {plot_path.absolute()}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
