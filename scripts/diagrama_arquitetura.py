#!/usr/bin/env python3
"""
Gera o diagrama de arquitetura do Digital Twin Processo Bayer (PNG dark-mode).

Correções aplicadas (v2):
- Glifos restritos aos suportados pela fonte DejaVu Sans (sem emojis *color* que
  renderizavam como "tofu" na fonte matplotlib padrão).
- Nó END reposicionado para evitar sobreposição com o painel INFRAESTRUTURA/influx.
- Typo corrigido: badge "MITL" -> "HITL".
- Semântica das setas corrigida (estável = caminho nao-crítico; concluído = pós-ação).
- Removido nó ficticio "plant_sensor_config.csv" (não existe no projeto).
"""
import os
import argparse
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.axes import Axes

# =============================================================================
# PALETA DE CORES
# =============================================================================
BG = "#0B0F19"
PANEL_BG = "#111827"
PANEL_BORDER = "#1F2937"
BOX_BG = "#141C2E"
TEXT_MAIN = "#F3F4F6"
TEXT_MUTED = "#9CA3AF"
BLUE_FLOW = "#38BDF8"       # nos do LangGraph
AMBER_WARN = "#F59E0B"      # decisao critica / HITL
GREEN_SUCCESS = "#10B981"   # termino / persistencia
GRAY_EXT = "#4B5563"        # modulos externos
BADGE_BG = "#1E293B"
ARROW_MUTED = "#64748B"

FIG_W, FIG_H, DPI = 14.0, 9.2, 220


# =============================================================================
# FUNCOES AUXILIARES DE DESENHO
# =============================================================================
def draw_panel(ax: Axes, x0: float, y0: float, w: float, h: float, title: str) -> None:
    """Desenha um container de modulo com cantos arredondados e cabecalho."""
    ax.add_patch(
        FancyBboxPatch(
            (x0, y0), w, h,
            boxstyle="round,pad=0.5,rounding_size=1.2",
            fc=PANEL_BG, ec=PANEL_BORDER, lw=1.2, zorder=0
        )
    )
    ax.text(
        x0 + 1.2, y0 + h - 1.8, title,
        color="#60A5FA", fontsize=8.5, ha="left", va="center",
        fontweight="bold", style="italic", zorder=1
    )


def draw_node(
    ax: Axes, cx: float, cy: float, w: float, h: float,
    name: str, sub: str, border_color: str,
    icon: str = "", badge: str = "",
    fs: float = 9.0, sfs: float = 7.5
) -> tuple[float, float, float, float]:
    """Desenha um no com icone (glifo DejaVu), titulo, subtitulo e badge."""
    ax.add_patch(
        FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle="round,pad=0.35,rounding_size=0.8",
            fc=BOX_BG, ec=border_color, lw=1.5, zorder=2
        )
    )

    if icon:
        ax.text(
            cx - w / 2 + 1.6, cy, icon,
            color=border_color, fontsize=fs * 1.25, ha="center", va="center", zorder=4
        )

    tx_offset = 1.2 if icon else 0.0
    y_name = cy + (h * 0.16 if sub else 0)
    ax.text(
        cx + tx_offset, y_name, name,
        color=TEXT_MAIN, fontsize=fs, ha="center", va="center",
        fontweight="bold", zorder=3
    )

    if sub:
        ax.text(
            cx + tx_offset, cy - h * 0.18, sub,
            color=TEXT_MUTED, fontsize=sfs, ha="center", va="center", zorder=3
        )

    if badge:
        bw, bh = len(badge) * 0.55 + 1.0, 1.8
        bx, by = cx + w / 2 - bw / 2 - 0.5, cy - h / 2 + bh / 2 + 0.5
        ax.add_patch(
            FancyBboxPatch(
                (bx - bw / 2, by - bh / 2), bw, bh,
                boxstyle="round,pad=0.15,rounding_size=0.4",
                fc=BADGE_BG, ec=border_color, lw=0.8, zorder=4
            )
        )
        ax.text(
            bx, by, badge,
            color=TEXT_MAIN, fontsize=6.2, ha="center", va="center",
            fontweight="bold", zorder=5
        )

    return (cx, cy, w, h)


def draw_arrow(
    ax: Axes, p0: tuple[float, float], p1: tuple[float, float],
    label: str | None = None, color: str = ARROW_MUTED, style: str = "-|>",
    lw: float = 1.4, ls: str = "-", lx: float = 0.0, ly: float = 0.0,
    fs: float = 7.5
) -> None:
    """Desenha conexoes direcionais com rotulo opcional."""
    ax.add_patch(
        FancyArrowPatch(
            p0, p1, arrowstyle=style, mutation_scale=12,
            color=color, lw=lw, linestyle=ls, zorder=1
        )
    )
    if label:
        ax.text(
            (p0[0] + p1[0]) / 2 + lx,
            (p0[1] + p1[1]) / 2 + ly,
            label, color=color, fontsize=fs,
            ha="center", va="center", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc=BG, ec=color, lw=0.6),
            zorder=6
        )


# =============================================================================
# RENDERIZACAO DO GRAFO
# =============================================================================
def main(output_path: str = "assets/arquitetura_processo_bayer.png") -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # ----- Titulo -----
    ax.text(50, 96.2,
            "Digital Twin do Processo Bayer — Agente de Controle (LangGraph)",
            color=TEXT_MAIN, fontsize=14, ha="center", va="center", fontweight="bold")
    ax.text(50, 92.2,
            "Supervisão de decantadores  |  Controle Fuzzy Adaptativo  |  Human In The Loop (HITL)",
            color=TEXT_MUTED, fontsize=9.2, ha="center", va="center")

    # ----- Paineis -----
    draw_panel(ax, 2, 8, 20, 78, "ENTRADAS")
    draw_panel(ax, 80, 36, 18, 50, "INFRAESTRUTURA")
    draw_panel(ax, 80, 6, 18, 26, "CONTROLE")

    pos = {}

    # ----- ENTRADAS (2 nos reais) -----
    pos["simulator"] = draw_node(
        ax, 12, 70, 16, 9, "bayer_process_\nsimulator.py", "Gêmeo Digital",
        border_color=GRAY_EXT, icon="⚙")
    pos["weather"] = draw_node(
        ax, 12, 40, 16, 9, "weather_service.py", "OpenWeather API",
        border_color=GRAY_EXT, icon="☁")

    # ----- INFRAESTRUTURA & CONTROLE -----
    pos["dashboard"] = draw_node(
        ax, 89, 72, 17, 10, "dashboard.py", "Streamlit + Plotly",
        border_color=GRAY_EXT)
    pos["influx"] = draw_node(
        ax, 89, 52, 17, 10, "influx_persister.py", "InfluxDB Time-Series",
        border_color=GRAY_EXT)
    pos["fuzzy_ctrl"] = draw_node(
        ax, 89, 18, 17, 10, "adaptive_fuzzy_\ncontroller.py", "Fuzzy Adaptativo",
        border_color=GRAY_EXT, icon="∿∿", badge="CONTROLLER")

    # ----- Fluxo principal LangGraph -----
    pos["coleta"] = draw_node(
        ax, 38, 80, 24, 8.5, "coleta", "ler_sensores_planta",
        border_color=BLUE_FLOW, badge="DATA")
    pos["analise"] = draw_node(
        ax, 38, 66, 24, 8.5, "analise", "avaliar_risco_bayer",
        border_color=BLUE_FLOW, badge="ALGORITHM")
    pos["calcular"] = draw_node(
        ax, 38, 52, 24, 8.5, "calcular_controle", "Fuzzy Adaptativo (PA/PB)",
        border_color=BLUE_FLOW, icon="∿∿", badge="Fuzzy Logic")
    pos["aguardar"] = draw_node(
        ax, 62, 40, 23, 8.5, "aguardar_operador", "HITL / Validação Humana",
        border_color=AMBER_WARN, badge="HITL")
    pos["executar"] = draw_node(
        ax, 62, 28, 23, 8.5, "executar_controle", "acionamento de válvulas",
        border_color=BLUE_FLOW, badge="ACTUATOR")
    pos["END"] = draw_node(
        ax, 38, 15, 14, 8, "END", "Fim / Persistir",
        border_color=GREEN_SUCCESS)

    # =========================================================================
    # CONEXOES DO FLUXO LANGGRAPH
    # =========================================================================
    # 1. Coleta -> Análise
    draw_arrow(ax, (38, 75.75), (38, 70.25), color=BLUE_FLOW)
    # 2. Análise -> Calcular
    draw_arrow(ax, (38, 61.75), (38, 56.25), color=BLUE_FLOW)
    # 3. Calcular -> Aguardar (crítico)
    draw_arrow(ax, (50, 52), (50.5, 44.25), label="crítico ⚠", color=AMBER_WARN, lx=0, ly=1.6)
    # 4. Aguardar -> Executar (aprovado)
    draw_arrow(ax, (62, 35.75), (62, 32.25), label="aprovado ✓", color=AMBER_WARN, lx=-8.2, ly=0)
    # 5. Executar -> END (concluído)
    draw_arrow(ax, (62, 23.75), (45, 19), label="concluído ✓", color=GREEN_SUCCESS, lx=-1.0, ly=2.0)
    # 6. Calcular -> END (estável / não-crítico)
    draw_arrow(ax, (38, 47.75), (38, 19), label="estável", color=GREEN_SUCCESS, lx=8.5, ly=0)

    # =========================================================================
    # INTEGRACOES EXTERNAS (TRACEJADAS)
    # =========================================================================
    # Simulador -> Coleta
    draw_arrow(ax, (46, 70), (26, 80), ls="--", color=ARROW_MUTED)
    # Clima -> Análise
    draw_arrow(ax, (46, 40), (26, 64), ls="--", color=ARROW_MUTED)
    # Calcular -> Módulo Fuzzy (controle)
    draw_arrow(ax, (50, 48), (80.5, 20), ls="--", color=ARROW_MUTED)
    # Coleta -> Dashboard
    draw_arrow(ax, (50, 78), (80.5, 70), ls="--", color=ARROW_MUTED)
    # Coleta -> Influx (persistência)
    draw_arrow(ax, (50, 74), (80.5, 54), ls="--", color=ARROW_MUTED)
    # Feedback do fluxo para o Gêmeo
    draw_arrow(ax, (27, 68), (46, 72), label="feedback p/ Gêmeo", ls=":",
               color="#94A3B8", lx=6, ly=2)

    # ----- Rodape -----
    ax.text(50, 2.5,
            "Fluxo: coleta → análise → calcular_controle → [crítico] aguardar_operador → executar_controle → persistência",
            color=TEXT_MUTED, fontsize=8.2, ha="center", va="center", style="italic")

    fig.tight_layout(pad=0.8)
    fig.savefig(output_path, facecolor=BG, bbox_inches="tight")
    print(f"Diagrama salvo em: {output_path}")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gera o diagrama de arquitetura do Digital Twin Processo Bayer.")
    parser.add_argument("-o", "--output", default="assets/arquitetura_processo_bayer.png",
                        help="Caminho do arquivo de saída")
    args = parser.parse_args()
    main(args.output)