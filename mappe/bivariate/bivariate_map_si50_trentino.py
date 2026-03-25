#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["geopandas", "pandas", "matplotlib", "duckdb", "numpy"]
# ///
"""
Bivariate choropleth: esito Sì/No (soglia 50%) vs affluenza finale per comune
Versione Trentino (COD_PROV == 22) con etichette intelligenti per comuni selezionati.

- Esito voto: 4 classi su % Sì con soglia semantica al 50%
  (<40, 40-50, 50-60, >60)
- Affluenza: 2 classi (quantili)
- Palette: arancione per prevalenza NO, blu per prevalenza SI
"""

from pathlib import Path
import pathlib

import duckdb
import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ── CONFIG ────────────────────────────────────────────────────────────────────

BASE = pathlib.Path(__file__).parent.parent.parent
SCRUTINI = BASE / "data/20260322/scrutini_flat.csv"
GEOJSON = BASE / "tmp/Com01012026_g_WGS84.geojson"
OUT = pathlib.Path(__file__).parent / "bivariate_map_si50_trentino.png"

FILTRO_GEOJSON = "COD_PROV == 22"
FILTRO_SCRUTINI = None

TITOLO = (
    "Referendum 2026 – Analisi bivariata: esito del voto e affluenza\n"
    "per comune (Trentino)"
)

# % Sì: 4 classi con soglia semantica al 50%
N_SI = 4
BREAKS_SI = [0, 40, 50, 60, 100]

# Affluenza: 2 classi
N_VOT = 2

# Palette "No" (i=0..1, % Sì < 50%): toni arancio
C_NO_00 = np.array([255, 185, 100])  # no + bassa affluenza
C_NO_10 = np.array([240, 120, 25])   # no più forte + bassa affluenza
C_NO_01 = np.array([220, 135, 55])   # no + alta affluenza
C_NO_11 = np.array([190, 70, 5])     # no forte + alta affluenza

# Palette "Sì" (i=2..3, % Sì >= 50%): toni blu
C_SI_00 = np.array([215, 228, 245])  # sì + bassa affluenza
C_SI_10 = np.array([70, 130, 220])   # sì più forte + bassa affluenza
C_SI_01 = np.array([140, 155, 200])  # sì + alta affluenza
C_SI_11 = np.array([20, 40, 140])    # sì forte + alta affluenza

COMUNI_DA_ETICHETTARE = [
    "Trento",
    "Rovereto",
    "Riva del Garda",
    "Arco",
    "Pergine Valsugana",
    "Mori",
    "Lavis",
    "Mezzolombardo",
    "Ala",
    "Levico Terme",
    "Canazei",
    "Cavalese",
    "Tione di Trento",
    "Peio",
    "Storo",
    "Borgo Valsugana",
    "Pinzolo",
    "Dimaro Folgarida",
    "Malè",
    "Primiero San Martino di Castrozza",
    "Cles",
    "Borgo d'Anaunia",
    "Vermiglio",
    "Predazzo",
    "Moena",
    "Ledro",
    "Canal San Bovo",
    "Borgo Chiese",
]

ALIAS_COMUNI = {
    "Levico": "Levico Terme",
    "Pejo": "Peio",
    "Dimaro": "Dimaro Folgarida",
    "Fiera di Primiero": "Primiero San Martino di Castrozza",
    "Fondo": "Borgo d'Anaunia",
    "Molina di Ledro": "Ledro",
}

PUNTI_COLORE = "#111111"
PUNTI_DIM = 20
FONT_ETICHETTE = 8

OFFSET_ETICHETTE = {
    "Trento": (8, 6),
    "Rovereto": (8, -2),
    "Riva del Garda": (-16, 12),
    "Arco": (16, -12),
    "Pergine Valsugana": (8, -10),
    "Mori": (8, 6),
    "Lavis": (8, 6),
    "Mezzolombardo": (8, -10),
    "Ala": (8, 6),
    "Levico Terme": (8, 6),
    "Canazei": (8, 6),
    "Cavalese": (8, 6),
    "Tione di Trento": (8, 6),
    "Peio": (8, 6),
    "Storo": (8, 6),
    "Borgo Valsugana": (8, 6),
    "Pinzolo": (8, 6),
    "Dimaro Folgarida": (8, -10),
    "Malè": (8, 6),
    "Primiero San Martino di Castrozza": (8, 6),
    "Cles": (8, 6),
    "Borgo d'Anaunia": (8, 6),
    "Vermiglio": (8, 6),
    "Predazzo": (8, 6),
    "Moena": (8, 6),
    "Ledro": (8, 6),
    "Canal San Bovo": (8, 6),
    "Borgo Chiese": (8, 6),
}

NODATA = "#f0f0f0"


# ── FUNZIONI ──────────────────────────────────────────────────────────────────

LABELS_SI = [chr(65 + i) for i in range(N_SI)]   # A, B, C, D
LABELS_VOT = [str(i + 1) for i in range(N_VOT)]  # 1, 2


def bilinear(i: int, j: int) -> str:
    """Interpolazione bilineare separata per zona No (i<2) e Sì (i>=2)."""
    s = j / (N_VOT - 1) if N_VOT > 1 else 0
    if i < 2:  # zona No
        t = 1.0 - i
        c00, c10, c01, c11 = C_NO_00, C_NO_10, C_NO_01, C_NO_11
    else:      # zona Sì
        t = (i - 2) / 1.0
        c00, c10, c01, c11 = C_SI_00, C_SI_10, C_SI_01, C_SI_11

    rgb = (1 - t) * (1 - s) * c00 + t * (1 - s) * c10 + (1 - t) * s * c01 + t * s * c11
    return "#{:02x}{:02x}{:02x}".format(*np.clip(rgb, 0, 255).astype(int))


COLORS = {
    LABELS_SI[i] + LABELS_VOT[j]: bilinear(i, j)
    for i in range(N_SI)
    for j in range(N_VOT)
}


def normalizza_testo(s):
    if s is None:
        return ""
    s = str(s).strip().lower()
    repl = {
        "à": "a", "è": "e", "é": "e", "ì": "i", "ò": "o", "ù": "u",
        "'": "", "’": "", "-": " ", "/": " "
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    return " ".join(s.split())


def dedup_preserva_ordine(valori):
    visti = set()
    out = []
    for v in valori:
        k = normalizza_testo(v)
        if k and k not in visti:
            out.append(v)
            visti.add(k)
    return out


def costruisci_lookup_comuni(comuni_richiesti, alias_comuni):
    lookup = {}
    for nome in dedup_preserva_ordine(comuni_richiesti):
        lookup[normalizza_testo(nome)] = nome
    for alias, ufficiale in alias_comuni.items():
        lookup[normalizza_testo(alias)] = ufficiale
    return lookup


def trova_colonna_nome_comune(gdf):
    candidati = ["COMUNE", "DEN_COM", "DEN_UTS", "DENOM", "NAME", "NOME", "NOME_COMUNE"]
    disponibili = {c.upper(): c for c in gdf.columns}
    for c in candidati:
        if c in disponibili:
            return disponibili[c]
    for c in gdf.columns:
        cu = c.upper()
        if "COM" in cu or "DEN" in cu or "NOME" in cu or "NAME" in cu:
            return c
    raise ValueError("Colonna nome comune non trovata nel GeoJSON")


def genera_offset_candidati(offset_preferito=None):
    candidati = []
    if offset_preferito is not None:
        candidati.append(tuple(offset_preferito))
    basi = [
        (10, 8), (10, -8), (-10, 8), (-10, -8),
        (14, 0), (-14, 0), (0, 14), (0, -14),
        (18, 10), (18, -10), (-18, 10), (-18, -10),
        (24, 0), (-24, 0), (0, 24), (0, -24),
    ]
    for candidato in basi:
        if candidato not in candidati:
            candidati.append(candidato)
    return candidati


def bbox_overlap_area(bb1, bb2):
    x0 = max(bb1.x0, bb2.x0)
    y0 = max(bb1.y0, bb2.y0)
    x1 = min(bb1.x1, bb2.x1)
    y1 = min(bb1.y1, bb2.y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float((x1 - x0) * (y1 - y0))


def scegli_posizione_etichetta(fig, ax, x, y, testo, renderer, bboxes_esistenti, offset_preferito):
    migliore = None
    for dx, dy in genera_offset_candidati(offset_preferito):
        txt = ax.annotate(
            testo,
            xy=(x, y),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=FONT_ETICHETTE,
            color="#111111",
            ha="left" if dx >= 0 else "right",
            va="bottom" if dy >= 0 else "top",
            zorder=6,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85),
            arrowprops=dict(arrowstyle="-", color="#444444", lw=0.4, shrinkA=0, shrinkB=0),
        )
        txt.set_path_effects([pe.withStroke(linewidth=1.5, foreground="white")])
        fig.canvas.draw()
        bb = txt.get_window_extent(renderer=renderer).expanded(1.03, 1.10)

        overlap = sum(bbox_overlap_area(bb, other) for other in bboxes_esistenti)
        x_disp, y_disp = ax.transData.transform((x, y))
        dist = ((bb.x0 + bb.x1) / 2 - x_disp) ** 2 + ((bb.y0 + bb.y1) / 2 - y_disp) ** 2

        boundary = 0.0
        if bb.x0 < 0:
            boundary += (0 - bb.x0) ** 2
        if bb.y0 < 0:
            boundary += (0 - bb.y0) ** 2
        if bb.x1 > fig.bbox.x1:
            boundary += (bb.x1 - fig.bbox.x1) ** 2
        if bb.y1 > fig.bbox.y1:
            boundary += (bb.y1 - fig.bbox.y1) ** 2

        score = overlap * 1000 + boundary * 10 + dist
        if migliore is None or score < migliore[0]:
            migliore = (score, txt, bb)
        else:
            txt.remove()

        if overlap == 0 and boundary == 0:
            break

    return migliore[1], migliore[2]


def aggiungi_etichette_intelligenti(fig, ax, etichette_df):
    if etichette_df.empty:
        return

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bboxes = []
    visti = set()

    df_ord = etichette_df.copy()
    df_ord["label_len"] = df_ord["nome_label"].str.len()
    df_ord = df_ord.sort_values(["y", "label_len"], ascending=[False, False])

    for row in df_ord.itertuples():
        if row.nome_label in visti:
            continue
        visti.add(row.nome_label)

        offset_preferito = OFFSET_ETICHETTE.get(row.nome_label, (8, 6))
        _, bb = scegli_posizione_etichetta(
            fig, ax, row.x, row.y, row.nome_label, renderer, bboxes, offset_preferito
        )
        bboxes.append(bb)


# ── Carica e prepara dati ─────────────────────────────────────────────────────

filtro_extra = f"AND {FILTRO_SCRUTINI}" if FILTRO_SCRUTINI else ""

con = duckdb.connect()
df = con.execute(f"""
    SELECT
        cod_istat,
        CAST(REPLACE(perc_si,  ',', '.') AS DOUBLE) AS perc_si,
        CAST(REPLACE(perc_vot, ',', '.') AS DOUBLE) AS perc_vot
    FROM '{SCRUTINI}'
    WHERE livello = 'comune'
      AND replace(perc_si,  ',', '.')::double > 0
      AND replace(perc_vot, ',', '.')::double > 0
      {filtro_extra}
""").df()

# Classificazione
df["q_si"] = pd.cut(
    df["perc_si"],
    bins=BREAKS_SI,
    labels=LABELS_SI,
    include_lowest=True
)
df["q_vot"] = pd.qcut(
    df["perc_vot"],
    q=N_VOT,
    labels=LABELS_VOT,
    duplicates="drop"
)

df["bivar"] = df["q_si"].astype(str) + df["q_vot"].astype(str)
df["color"] = df["bivar"].map(COLORS)

q_breaks_vot = [i / N_VOT for i in range(N_VOT + 1)]
breaks_vot = [df["perc_vot"].quantile(q).round(1) for q in q_breaks_vot]


# ── GeoJSON + join ────────────────────────────────────────────────────────────

gdf = gpd.read_file(GEOJSON)
if FILTRO_GEOJSON:
    gdf = gdf.query(FILTRO_GEOJSON).copy()

gdf = gdf.merge(
    df[["cod_istat", "bivar", "color"]],
    left_on="PRO_COM_T",
    right_on="cod_istat",
    how="left"
)
gdf["color"] = gdf["color"].fillna(NODATA)
gdf = gdf.to_crs("EPSG:32632")


# ── Figura ────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(1, 1, figsize=(14, 14), facecolor="white")
ax.set_axis_off()
fig.patch.set_facecolor("white")

gdf.plot(ax=ax, color=gdf["color"], linewidth=0.05, edgecolor="#aaaaaa")

# Punti ed etichette
colonna_nome = trova_colonna_nome_comune(gdf)
gdf["nome_norm"] = gdf[colonna_nome].astype(str).map(normalizza_testo)

lookup_target = costruisci_lookup_comuni(COMUNI_DA_ETICHETTARE, ALIAS_COMUNI)
etichette = gdf[gdf["nome_norm"].isin(lookup_target)].copy()
etichette["nome_label"] = etichette["nome_norm"].map(lookup_target)

etichette = (
    etichette
    .drop_duplicates(subset=["nome_norm"], keep="first")
    .drop_duplicates(subset=["nome_label"], keep="first")
    .copy()
)

etichette["label_point"] = etichette.geometry.representative_point()
etichette["x"] = etichette["label_point"].x
etichette["y"] = etichette["label_point"].y

ax.scatter(
    etichette["x"],
    etichette["y"],
    s=PUNTI_DIM,
    color=PUNTI_COLORE,
    edgecolors="white",
    linewidths=0.5,
    zorder=5,
)
aggiungi_etichette_intelligenti(fig, ax, etichette)


# ── Legenda 4 × 2 ─────────────────────────────────────────────────────────────

# Più staccata dalla mappa
legend_ax = fig.add_axes([0.03, 0.06, 0.22, 0.22])
legend_ax.set_aspect("equal")
legend_ax.set_axis_off()

cell = 1.2

for i, col in enumerate(LABELS_SI):
    for j, row in enumerate(LABELS_VOT):
        legend_ax.add_patch(
            mpatches.FancyBboxPatch(
                (i * cell, j * cell),
                cell,
                cell,
                boxstyle="square,pad=0",
                facecolor=COLORS[col + row],
                edgecolor="white",
                linewidth=0.5,
            )
        )

# Linea verticale divisoria No/Sì tra i=1 e i=2
legend_ax.plot([2 * cell, 2 * cell], [0, N_VOT * cell], color="black", linewidth=2, zorder=5)

# Etichette No/Sì
legend_ax.text(
    1.0 * cell,
    (N_VOT * cell) / 2,
    "No",
    ha="center",
    va="center",
    fontsize=9,
    color="white",
    fontweight="bold",
    zorder=6,
)
legend_ax.text(
    3.0 * cell,
    (N_VOT * cell) / 2,
    "Sì",
    ha="center",
    va="center",
    fontsize=9,
    color="white",
    fontweight="bold",
    zorder=6,
)

legend_ax.set_xlim(-0.2, N_SI * cell + 0.4)
legend_ax.set_ylim(-0.7, N_VOT * cell + 0.4)

arrow_kw = dict(arrowstyle="->", color="#333333", lw=1.2)
legend_ax.annotate(
    "",
    xy=(N_SI * cell + 0.2, -0.18),
    xytext=(-0.1, -0.18),
    arrowprops=arrow_kw,
)
legend_ax.annotate(
    "",
    xy=(-0.18, N_VOT * cell + 0.2),
    xytext=(-0.18, -0.1),
    arrowprops=arrow_kw,
)

legend_ax.text(
    (N_SI * cell) / 2,
    -0.48,
    "% Sì →",
    ha="center",
    va="top",
    fontsize=7.5,
    color="#333333",
    fontweight="bold",
)
legend_ax.text(
    -0.42,
    (N_VOT * cell) / 2,
    "Affluenza →",
    ha="right",
    va="center",
    fontsize=7.5,
    color="#333333",
    fontweight="bold",
    rotation=90,
)

# Labels classi % Sì
si_labels = ["<40", "40-50", "50-60", ">60"]
for i, lab in enumerate(si_labels):
    legend_ax.text(
        i * cell + cell / 2,
        -0.06,
        lab,
        ha="center",
        va="top",
        fontsize=6.8,
        color="#333333",
    )

# Labels classi affluenza (2 classi)
vot_labels = [
    f"{breaks_vot[0]:.1f}–{breaks_vot[1]:.1f}",
    f"{breaks_vot[1]:.1f}–{breaks_vot[2]:.1f}",
]
for j, lab in enumerate(vot_labels):
    legend_ax.text(
        -0.05,
        j * cell + cell / 2,
        lab,
        ha="right",
        va="center",
        fontsize=6.6,
        color="#333333",
    )

# Titolo
ax.set_title(TITOLO, fontsize=20, fontweight="bold")


# ── Salvataggio ───────────────────────────────────────────────────────────────

plt.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
svg_output = OUT.with_suffix(".svg")
pdf_output = OUT.with_suffix(".pdf")
plt.savefig(svg_output, format="svg", bbox_inches="tight", facecolor="white")
plt.savefig(pdf_output, format="pdf", bbox_inches="tight", facecolor="white")

print(f"Creato anche SVG: {svg_output}")
print(f"Creato anche PDF: {pdf_output}")
print(f"Salvato: {OUT}")
