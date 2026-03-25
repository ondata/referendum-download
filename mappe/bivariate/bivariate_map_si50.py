#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["geopandas", "pandas", "matplotlib", "duckdb", "numpy"]
# ///
"""
Bivariate choropleth: % Sì vs % Affluenza finale per comune - Referendum 2026
% Sì: 4 classi con soglia semantica al 50% (<40, 40-50, 50-60, >60)
% Affluenza: 3 classi (terzili)
Palette: schema Trumbo (1981) rosso-viola-blu, legenda parallelogramma a 45°.
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import duckdb
import numpy as np
import pathlib

# ── CONFIG ────────────────────────────────────────────────────────────────────

BASE     = pathlib.Path(__file__).parent.parent.parent
SCRUTINI = BASE / "data/20260322/scrutini_flat.csv"
GEOJSON  = BASE / "tmp/Com01012026_g_WGS84.geojson"
OUT      = pathlib.Path(__file__).parent / "bivariate_map_si50.png"

# Classi % Sì: breaks semantici con soglia al 50%
N_SI      = 4
BREAKS_SI = [0, 40, 50, 60, 100]

# Classi % Affluenza: terzili
N_VOT = 3

# Palette "No" (i=0..1, % Sì < 50%): toni caldi giallo/arancio
C_NO_00 = np.array([235, 230, 215])  # grigio caldo (basso si, bassa affl)
C_NO_10 = np.array([255, 165,  50])  # arancio (alto si No, bassa affl)
C_NO_01 = np.array([185, 165, 110])  # grigio scuro caldo (basso si, alta affl)
C_NO_11 = np.array([200,  90,  15])  # arancio scuro (alto si No, alta affl)

# Palette "Sì" (i=2..3, % Sì >= 50%): toni freddi blu
C_SI_00 = np.array([215, 228, 245])  # grigio freddo (basso si Sì, bassa affl)
C_SI_10 = np.array([ 70, 130, 220])  # blu (alto si, bassa affl)
C_SI_01 = np.array([140, 155, 200])  # grigio-blu scuro (basso si Sì, alta affl)
C_SI_11 = np.array([ 20,  40, 140])  # blu scuro/viola (alto si, alta affl)

FILTRO_GEOJSON  = None
FILTRO_SCRUTINI = None
TITOLO = None

# ── FINE CONFIG ───────────────────────────────────────────────────────────────

LABELS_SI  = [chr(65 + i) for i in range(N_SI)]   # A, B, C, D
LABELS_VOT = [str(i + 1)  for i in range(N_VOT)]  # 1, 2, 3


def bilinear(i, j):
    """Interpolazione bilineare separata per zona No (i<2) e Sì (i>=2)."""
    s = j / (N_VOT - 1)
    if i < 2:  # zona No
        t = i / 1.0
        C00, C10, C01, C11 = C_NO_00, C_NO_10, C_NO_01, C_NO_11
    else:      # zona Sì
        t = (i - 2) / 1.0
        C00, C10, C01, C11 = C_SI_00, C_SI_10, C_SI_01, C_SI_11
    rgb = (1 - t) * (1 - s) * C00 + t * (1 - s) * C10 + (1 - t) * s * C01 + t * s * C11
    return '#{:02x}{:02x}{:02x}'.format(*np.clip(rgb, 0, 255).astype(int))


COLORS = {
    LABELS_SI[i] + LABELS_VOT[j]: bilinear(i, j)
    for i in range(N_SI)
    for j in range(N_VOT)
}
NODATA = '#f0f0f0'

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

df['q_si']  = pd.cut(df['perc_si'], bins=BREAKS_SI, labels=LABELS_SI, include_lowest=True)
df['q_vot'] = pd.qcut(df['perc_vot'], q=N_VOT, labels=LABELS_VOT, duplicates='drop')
df['bivar'] = df['q_si'].astype(str) + df['q_vot'].astype(str)
df['color'] = df['bivar'].map(COLORS)

Q_BREAKS_VOT = [i / N_VOT for i in range(N_VOT + 1)]
breaks_vot = [df['perc_vot'].quantile(q).round(1) for q in Q_BREAKS_VOT]

# ── GeoJSON + join ────────────────────────────────────────────────────────────
gdf = gpd.read_file(GEOJSON)
if FILTRO_GEOJSON:
    gdf = gdf.query(FILTRO_GEOJSON).copy()
gdf = gdf.merge(
    df[['cod_istat', 'bivar', 'color']],
    left_on='PRO_COM_T', right_on='cod_istat',
    how='left'
)
gdf['color'] = gdf['color'].fillna(NODATA)
gdf = gdf.to_crs('EPSG:32632')

# ── Figura ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(1, 1, figsize=(14, 14), facecolor='white')
ax.set_axis_off()
fig.patch.set_facecolor('white')

gdf.plot(ax=ax, color=gdf['color'], linewidth=0.05, edgecolor='#aaaaaa')

# ── Legenda 45° (parallelogramma N_SI × N_VOT) ────────────────────────────────
legend_ax = fig.add_axes([0.04, 0.06, 0.25, 0.25])
legend_ax.set_aspect('equal')
legend_ax.set_axis_off()

for i, col in enumerate(LABELS_SI):
    for j, row in enumerate(LABELS_VOT):
        cx = float(i - j)
        cy = float(i + j + 1)
        corners = [(cx, cy - 1), (cx + 1, cy), (cx, cy + 1), (cx - 1, cy)]
        legend_ax.add_patch(mpatches.Polygon(
            corners, closed=True,
            facecolor=COLORS[col + row],
            edgecolor='white', linewidth=0.5))

# Linea nera divisoria No/Sì al 50% (bordo tra i=1 e i=2)
# Punti condivisi: (2-j, 2+j) → (1-j, 3+j) per j=0..N_VOT-1
x_div = [2, 2 - (N_VOT - 1) - 1]   # da (2,2) a (-1,5) per N_VOT=3
y_div = [2, 2 + (N_VOT - 1) + 1]
legend_ax.plot(x_div, y_div, color='black', linewidth=2,
               solid_capstyle='round', zorder=5)

# Etichette No/Sì sui due lati della linea
legend_ax.text(-0.5, 2.5, 'No', ha='center', va='center',
               fontsize=9, color='white', fontweight='bold', zorder=6)
legend_ax.text(1.5, 4.5, 'Sì', ha='center', va='center',
               fontsize=9, color='white', fontweight='bold', zorder=6)

# range uguale su x e y per aspect='equal'
legend_ax.set_xlim(-N_VOT - 1, N_SI + 1)           # range = N_SI + N_VOT + 2 = 9
legend_ax.set_ylim(-1.5, N_SI + N_VOT + 0.5)       # range = 9

arrow_kw = dict(arrowstyle='->', color='#333333', lw=1.2)
legend_ax.annotate('', xy=(N_SI + 0.4, N_SI + 0.4), xytext=(0, 0), arrowprops=arrow_kw)
legend_ax.annotate('', xy=(-N_VOT - 0.4, N_VOT + 0.4), xytext=(0, 0), arrowprops=arrow_kw)

legend_ax.text(N_SI / 2 + 0.7, N_SI / 2 - 0.7, '% Sì →', ha='center', va='center',
               fontsize=7.5, color='#333333', fontweight='bold', rotation=45)
legend_ax.text(-N_VOT / 2 - 0.7, N_VOT / 2 - 0.7, '← % Affluenza', ha='center', va='center',
               fontsize=7.5, color='#333333', fontweight='bold', rotation=-45)

# ── Titolo e note ─────────────────────────────────────────────────────────────
titolo = TITOLO or (
    'Referendum 2026 – Bivariata: % Sì × % Affluenza finale\n'
    'per comune (% Sì: soglia 50%; affluenza: terzili)'
)
ax.set_title(titolo, fontsize=14, fontweight='bold', pad=16, color='#222222')

si_str  = '  '.join(f'[{BREAKS_SI[k]}–{BREAKS_SI[k+1]}]' for k in range(N_SI))
vot_str = '  '.join(f'[{breaks_vot[k]}–{breaks_vot[k+1]}]' for k in range(N_VOT))
fig.text(0.08, 0.07,
         f"% Sì:        {si_str}\n"
         f"% Affluenza: {vot_str}",
         fontsize=7, color='#555555', family='monospace')

fig.text(0.92, 0.04, 'Fonte: Eligendo / ISTAT', ha='right',
         fontsize=8, color='#888888')

plt.savefig(OUT, dpi=200, bbox_inches='tight', facecolor='white')
print(f"Salvato: {OUT}")
