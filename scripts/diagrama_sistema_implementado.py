#!/usr/bin/env python3
"""Gera o diagrama dark-mode da VISÃO DO SISTEMA IMPLEMENTADO (em subgrafos).

Layout: Entradas -> Gêmeo Digital -> Agente ; Persistência (lado) ; Saídas (abaixo).
```
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

BG      = "#0B0F19"
PANEL   = "#111827"
PN_BORD = "#1F2937"
BOX     = "#151C2E"
TXT     = "#E6EDF3"
MUTED   = "#9AA7B5"
BLUE    = "#38BDF8"
GREEN   = "#10B981"
AMBER   = "#F59E0B"
GRAY    = "#4B5563"

FIG_W, FIG_H, DPI = 13.6, 8.6, 200


def panel(ax, x0, y0, w, h, title, accent):
    ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0.5,rounding_size=1.1",
                               fc=PANEL, ec=PN_BORD, lw=1.0, zorder=0))
    ax.add_patch(FancyBboxPatch((x0, y0), w, 2.0, boxstyle="round,pad=0.4,rounding_size=0.9",
                               fc=accent, ec=accent, lw=0, zorder=1))
    ax.text(x0 + 0.7, y0 + 1.0, title, color="#0B0F19", fontsize=8.5, ha="left",
            va="center", fontweight="bold", zorder=2)


def node(ax, cx, cy, w, h, lines, color):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                               boxstyle="round,pad=0.25,rounding_size=0.6",
                               fc=BOX, ec=color, lw=1.0, zorder=2))
    if len(lines) == 1:
        ax.text(cx, cy, lines[0], color=TXT, fontsize=6.8, ha="center", va="center",
                fontweight="bold", zorder=3)
    else:
        ax.text(cx, cy + h * 0.14, lines[0], color=TXT, fontsize=6.8, ha="center",
                va="center", fontweight="bold", zorder=3)
        ax.text(cx, cy - h * 0.16, lines[1], color=MUTED, fontsize=6.0, ha="center",
                va="center", zorder=3)


def arr(ax, p0, p1, color=GRAY, ls="-", lw=1.3, label=None, lx=0, ly=0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=11,
                                color=color, lw=lw, linestyle=ls, zorder=1))
    if label:
        ax.text((p0[0] + p1[0]) / 2 + lx, (p0[1] + p1[1]) / 2 + ly, label, color=color,
                fontsize=6.5, ha="center", va="center", style="italic", zorder=2)


def vstack(ax, left, right, ytop, ybot, nodes, color):
    """Empilha boxes verticalmente dentro de um painel (left..right, ytop..ybot)."""
    n = len(nodes)
    pad = 0.8
    box_h = min(6.5, (ybot - ytop) / n - pad)
    y = ytop + box_h / 2
    for lines in nodes:
        node(ax, (left + right) / 2, y, right - left, box_h, lines, color)
        y += box_h + pad


def main():
    os.makedirs("assets", exist_ok=True)
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 96.5, "Sistema Implementado — Digital Twin do Processo Bayer",
            color=TXT, fontsize=14, ha="center", va="center", fontweight="bold")
    ax.text(50, 93.3, "Entradas → Gêmeo Digital → Agente (LangGraph) → Persistência/Saídas",
            color=MUTED, fontsize=9, ha="center", va="center", style="italic")

    # ---- Painéis superiores ----
    panel(ax, 2, 42, 21, 50, "ENTRADAS", BLUE)            # 2..23, y 42..92
    panel(ax, 26, 42, 21, 50, "GÊMEO DIGITAL", GREEN)     # 26..47
    panel(ax, 50, 42, 23, 50, "AGENTE (LangGraph)", BLUE) # 50..73
    panel(ax, 76, 54, 22, 38, "PERSISTÊNCIA", GRAY)       # 76..98, y 54..92

    # ---- Painel inferior ----
    panel(ax, 50, 6, 23, 32, "SAÍDAS DO PROCESSO", AMBER) # 50..73, y 6..38

    vstack(ax, 3.5, 21.5, 90, 47, [
        ["Bauxita", "vazão + teor de sílica"],
        ["Lavagem / Condensado", "diluição do TC"],
        ["Chuva", "OpenWeather (atual + 6h)"],
        ["Distúrbios", "desgaste, stiction, desbal."],
    ], BLUE)

    vstack(ax, 27.5, 45.5, 90, 47, [
        ["Digestores em SÉRIE", "S1 → S2"],
        ["Decantadores PARALELO", "PA e PB (150 m²)"],
        ["Balanço Massa + Química", "TC e perda de soda"],
        ["Gerador de Distúrbios", "estocásticos"],
    ], GREEN)

    vstack(ax, 51.5, 71.5, 90, 43, [
        ["Coleta", "sensores + clima + EMA"],
        ["Análise de Risco", "nível + derivada (EMA)"],
        ["Controle Fuzzy Adapt.", "ganho γ por tanque"],
        ["Human-in-the-Loop", "aprovação obrigatória"],
        ["Execução Física", "válvulas modulantes"],
    ], BLUE)

    vstack(ax, 77.5, 95.5, 90, 58, [
        ["InfluxDB", "séries temporais"],
        ["Dashboard", "Streamlit / KPIs"],
        ["Logs e Alertas", "HITL, distúrbios"],
    ], GRAY)

    vstack(ax, 51.5, 71.5, 34, 10, [
        ["Lama Vermelha", "perda de soda"],
        ["Licor Clarificado", "p/ precipitação"],
        ["Nível controlado", "setpoint 65%"],
    ], AMBER)

    # ---- Fluxo principal ----
    arr(ax, (23, 70), (26, 70), color=BLUE, lw=1.6)
    arr(ax, (47, 70), (50, 70), color=GREEN, lw=1.6)
    arr(ax, (73, 62), (76, 62), color=GRAY, lw=1.5, label="persistência", ly=0)
    arr(ax, (61.5, 42), (61.5, 38), color=AMBER, lw=1.5, label="saídas", lx=-4.5, ly=0)

    # ---- Realimentação (tracejadas) ----
    arr(ax, (78, 57), (71.5, 50), color=GRAY, ls=(0, (3, 2)), label="realimentação", lx=-6, ly=1)
    arr(ax, (50, 30), (40, 42), color=GRAY, ls=(0, (3, 2)), label="medições", lx=-2, ly=2)

    ax.text(50, 2.8, "Fluxo: Entradas → Gêmeo Digital → Agente → Persistência/Saídas ; realimentação tracejada",
            color=MUTED, fontsize=7.5, ha="center", va="center", style="italic")

    fig.tight_layout(pad=0.6)
    out = "assets/arquitetura_sistema_implementado.png"
    fig.savefig(out, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    print("OK:", out)


if __name__ == "__main__":
    main()