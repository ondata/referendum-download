#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["geopandas", "pandas", "matplotlib", "duckdb", "numpy"]
# ///
"""
Bivariate choropleth: % Sì vs % Affluenza finale per comune - Referendum 2026
Schema colori HSL "lightness × hue":
  - hue:       rosso/corallo (No) → viola → blu (Sì)
  - lightness: chiaro (bassa affluenza) → scuro (alta affluenza)
"""

import colorsys
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
OUT      = pathlib.Path(__file__).parent / "bivariate_map_simone.png"

# Classi
N_SI  = 3   # terzili % Sì
N_VOT = 3   # terzili % Affluenza

# Schema HSL
HUE_NO  = 355   # rosso/corallo (+No, i=0)
HUE_SI  = 230   # blu (+Sì, i=N_SI-1)
SAT     = 0.55  # saturazione fissa
L_LOW   = 0.82  # lightness bassa affluenza (chiaro)
L_HIGH  = 0.38  # lightness alta affluenza (scuro)

FILTRO_GEOJSON  = None
FILTRO_SCRUTINI = None
TITOLO = None

# ── FINE CONFIG ───────────────────────────────────────────────────────────────

LABELS_SI  = [chr(65 + i) for i in range(N_SI)]   # A, B, C
LABELS_VOT = [str(i + 1)  for i in range(N_VOT)]  # 1, 2, 3, 4


def hsl_color(i, j):
    """Colore HSL: hue varia con % Sì (No→Sì), lightness con affluenza (bassa→alta)."""
    h = (HUE_NO + (HUE_SI - HUE_NO) * i / (N_SI - 1)) % 360
    l = L_LOW - (L_LOW - L_HIGH) * j / (N_VOT - 1)
    r, g, b = colorsys.hls_to_rgb(h / 360, l, SAT)
    return '#{:02x}{:02x}{:02x}'.format(int(r * 255), int(g * 255), int(b * 255))


COLORS = {
    LABELS_SI[i] + LABELS_VOT[j]: hsl_color(i, j)
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

df['q_si']  = pd.qcut(df['perc_si'],  q=N_SI,  labels=LABELS_SI,  duplicates='drop')
df['q_vot'] = pd.qcut(df['perc_vot'], q=N_VOT, labels=LABELS_VOT, duplicates='drop')
df['bivar'] = df['q_si'].astype(str) + df['q_vot'].astype(str)
df['color'] = df['bivar'].map(COLORS)

breaks_si  = [df['perc_si'].quantile(i / N_SI).round(1)  for i in range(N_SI  + 1)]
breaks_vot = [df['perc_vot'].quantile(i / N_VOT).round(1) for i in range(N_VOT + 1)]

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

# ── Legenda griglia N_SI × N_VOT ──────────────────────────────────────────────
legend_ax = fig.add_axes([0.05, 0.15, 0.15, 0.15])
legend_ax.set_aspect('equal')
legend_ax.set_axis_off()

cell = 1.0
for i, col in enumerate(LABELS_SI):
    for j, row in enumerate(LABELS_VOT):
        legend_ax.add_patch(mpatches.FancyBboxPatch(
            (i * cell, j * cell), cell, cell,
            boxstyle="square,pad=0",
            facecolor=COLORS[col + row],
            edgecolor='white', linewidth=0.5))

legend_ax.set_xlim(-0.1, N_SI + 0.3)
legend_ax.set_ylim(-0.5, N_VOT + 0.3)

arrow_kw = dict(arrowstyle='->', color='#333333', lw=1.2)
legend_ax.annotate('', xy=(N_SI + 0.2, -0.15), xytext=(-0.1, -0.15), arrowprops=arrow_kw)
legend_ax.annotate('', xy=(-0.15, N_VOT + 0.2), xytext=(-0.15, -0.1), arrowprops=arrow_kw)

legend_ax.text(N_SI / 2, -0.4, '% Sì →', ha='center', va='top',
               fontsize=7.5, color='#333333', fontweight='bold')
legend_ax.text(-0.35, N_VOT / 2, '% Affluenza →', ha='right', va='center',
               fontsize=7.5, color='#333333', fontweight='bold', rotation=90)

# ── Titolo e note ─────────────────────────────────────────────────────────────
titolo = TITOLO or (
    'Referendum 2026 – Bivariata: % Sì × % Affluenza finale\n'
    'per comune (terzili % Sì; terzili affluenza)'
)
ax.set_title(titolo, fontsize=14, fontweight='bold', pad=16, color='#222222')

si_str  = '  '.join(f'[{breaks_si[k]}–{breaks_si[k+1]}]'  for k in range(N_SI))
vot_str = '  '.join(f'[{breaks_vot[k]}–{breaks_vot[k+1]}]' for k in range(N_VOT))
fig.text(0.08, 0.04,
         f"% Sì:        {si_str}\n"
         f"% Affluenza: {vot_str}",
         fontsize=7, color='#555555', family='monospace')

fig.text(0.92, 0.04, 'Fonte: Eligendo / ISTAT', ha='right',
         fontsize=8, color='#888888')

plt.savefig(OUT, dpi=200, bbox_inches='tight', facecolor='white')
print(f"Salvato: {OUT}")
