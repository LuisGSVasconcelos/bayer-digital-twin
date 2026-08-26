"""Gera o diagrama de arquitetura do Digital Twin Processo Bayer (PNG dark-mode)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BG = "#0d1117"
PANEL = "#161b22"
TEXT = "#e6edf3"
FLOW = "#58a6ff"      # nos do grafo LangGraph
AMBER = "#d29922"     # HITL
GREEN = "#3fb950"     # END
GRAY = "#8b949e"      # modulos externos
ARROW = "#8b949e"

FIG_W, FIG_H, DPI = 12.6, 8.2, 200


def panel(ax, x0, y0, w, h, title):
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0.6,rounding_size=1.2",
                                fc=PANEL, ec=GRAY, lw=0.8, zorder=0))
    ax.text(x0 + 1.2, y0 + h - 1.6, title, color=TEXT, fontsize=9, ha="left",
            va="center", style="italic")


def box(ax, cx, cy, w, h, name, sub, fc, ec, fs=9.5, sfs=7.5):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle="round,pad=0.35,rounding_size=0.8",
                                fc=fc, ec=ec, lw=1.4, zorder=2))
    ax.text(cx, cy + h * 0.16 if sub else cy, name, color=TEXT, fontsize=fs,
            ha="center", va="center", fontweight="bold", zorder=3)
    if sub:
        ax.text(cx, cy - h * 0.18, sub, color=GRAY, fontsize=sfs, ha="center",
                va="center", zorder=3)
    return (cx, cy, w, h)


def arrow(ax, p0, p1, label=None, color=ARROW, style="-|>", lw=1.4, ls="-",
          lx=0.0, ly=0.0, fs=8):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                                 color=color, lw=lw, linestyle=ls, zorder=1))
    if label:
        ax.text((p0[0] + p1[0]) / 2 + lx, (p0[1] + p1[1]) / 2 + ly, label,
                color=color, fontsize=fs, ha="center", va="center",
                bbox=dict(fc=BG, ec="none", pad=0.8), zorder=3)


def main():
    os.makedirs("assets", exist_ok=True)
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 97, "Digital Twin do Processo Bayer — Agente de Controle (LangGraph)",
            color=TEXT, fontsize=15, ha="center", va="center", fontweight="bold")
    ax.text(50, 92.6, "Supervisão de decantadores | Controle Fuzzy Adaptativo | HITL",
            color=GRAY, fontsize=10, ha="center", va="center")

    # ----- paineis externos -----
    panel(ax, 2, 26, 20, 50, "ENTRADAS")
    panel(ax, 78, 30, 20, 50, "INFRAESTRUTURA")
    panel(ax, 78, 6, 20, 22, "CONTROLE")

    box(ax, 12, 72, 16, 9, "bayer_process_\nsimulator.py", "Gêmeo Digital", PANEL, FLOW,
        fs=7.5, sfs=7)
    box(ax, 12, 58, 16, 9, "weather_service.py", "OpenWeather", PANEL, FLOW,
        fs=7.5, sfs=7)

    box(ax, 88, 74, 17, 10, "dashboard.py", "Streamlit + Plotly", PANEL, GRAY,
        fs=8, sfs=7)
    box(ax, 88, 58, 17, 10, "influx_persister.py", "InfluxDB", PANEL, GRAY,
        fs=8, sfs=7)
    box(ax, 88, 14, 17, 10, "adaptive_fuzzy_\ncontroller.py", "Fuzzy Adaptativo", PANEL, GRAY,
        fs=7.5, sfs=7)

    # ----- fluxo LangGraph -----
    flow = PANEL
    box(ax, 34, 82, 22, 8, "coleta", "ler_sensores_planta", flow, FLOW)
    box(ax, 34, 70, 22, 8, "analise", "avaliar_risco_bayer", flow, FLOW)
    box(ax, 34, 58, 24, 8, "calcular_controle", "Fuzzy Adaptativo (PA/PB)", flow, FLOW)
    box(ax, 56, 40, 20, 8, "aguardar_operador", "HITL", flow, AMBER)
    box(ax, 56, 28, 22, 8, "executar_controle", "abre válvulas", flow, FLOW)
    box(ax, 80, 58, 12, 7, "END", "ciclo concluído", flow, GREEN)

    # ----- setas do fluxo -----
    arrow(ax, (34, 78), (34, 74))
    arrow(ax, (34, 66), (34, 62))
    arrow(ax, (46, 58), (54, 43.5), label="crítico", color=AMBER, lx=-1.4, ly=1.6)
    arrow(ax, (56, 36), (56, 32), label="aprovado", color=AMBER, lx=-7.2, ly=0)
    arrow(ax, (67, 28), (78, 55), label="estável → END", color=GRAY, lx=0, ly=3)
    arrow(ax, (46, 58), (74, 58), color=GREEN, lx=0, ly=0)

    # ----- dependencias (tracejadas) -----
    arrow(ax, (20, 72), (23, 81), ls=(0, (3, 2)), color=GRAY)
    arrow(ax, (55, 58), (79, 14), ls=(0, (3, 2)), color=GRAY, style="-|>")
    arrow(ax, (23, 78), (34, 80), ls=(0, (3, 2)), color=GRAY)
    arrow(ax, (59, 44), (88, 58), ls=(0, (3, 2)), color=GRAY)

    ax.text(50, 3.2, "Fluxo: coleta → analise → calcular_controle → [crítico] aguardar_operador → executar_controle",
            color=GRAY, fontsize=8.5, ha="center", va="center", style="italic")

    fig.tight_layout(pad=0.6)
    out = "assets/arquitetura_processo_bayer.png"
    fig.savefig(out, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    print(f"OK: {out}")


if __name__ == "__main__":
    main()