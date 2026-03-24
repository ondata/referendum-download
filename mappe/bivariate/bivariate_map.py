#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["geopandas", "pandas", "matplotlib", "duckdb", "numpy"]
# ///
"""
Bivariate choropleth: % Sì vs % Affluenza finale per comune - Referendum 2026
Palette: interpolazione bilineare dagli angoli Stevens (teal × pink/violet)

Personalizzazione: vedi sezione "CONFIG" qui sotto.
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import duckdb
import numpy as np
import pathlib

# ── CONFIG ────────────────────────────────────────────────────────────────────

# Percorsi input/output
BASE     = pathlib.Path(__file__).parent.parent.parent
SCRUTINI = BASE / "data/20260322/scrutini_flat.csv"
GEOJSON  = BASE / "tmp/Com01012026_g_WGS84.geojson"
OUT      = pathlib.Path(__file__).parent / "bivariate_map.png"

# Numero di classi per asse (es. 3=terzili, 4=quartili, 5=quintili)
N = 5

# Colori ai 4 angoli della griglia (RGB). Modifica per cambiare palette.
# (si_basso, vot_basso) → (si_alto, vot_basso)
# (si_basso, vot_alto)  → (si_alto, vot_alto)
C00 = np.array([232, 232, 232])  # grigio chiaro
C_N0 = np.array([90,  200, 200])  # teal
C0_N = np.array([190, 100, 172])  # viola/rosa
C_NN = np.array([59,   73, 148])  # blu scuro

# Filtro territoriale: None = tutti i comuni
# Esempi: COD_REG == 19 (Sicilia), COD_REG == 15 (Campania)
FILTRO_GEOJSON = None  # es: "COD_REG == 19"

# Filtro dati scrutini: None = tutti i comuni
# Esempi: "cod_reg = '19'", "cod_reg = '01'"
FILTRO_SCRUTINI = None  # es: "AND cod_reg = '19'"

# Titolo mappa (None = generato automaticamente)
TITOLO = None

# ── FINE CONFIG ───────────────────────────────────────────────────────────────

# Etichette classi
LABELS_SI  = [chr(65 + i) for i in range(N)]   # A, B, C, ...
LABELS_VOT = [str(i + 1)  for i in range(N)]   # 1, 2, 3, ...

# Quantili equidistanti
Q_BREAKS = [i / N for i in range(N + 1)]


def bilinear(i, j):
    """Interpolazione bilineare per cella (i=col/si, j=row/vot), indici 0-based."""
    t, s = i / (N - 1), j / (N - 1)
    rgb = ((1 - t) * (1 - s) * C00
           + t * (1 - s) * C_N0
           + (1 - t) * s * C0_N
           + t * s * C_NN)
    return '#{:02x}{:02x}{:02x}'.format(*np.clip(rgb, 0, 255).astype(int))


COLORS = {
    LABELS_SI[i] + LABELS_VOT[j]: bilinear(i, j)
    for i in range(N)
    for j in range(N)
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

df['q_si']  = pd.qcut(df['perc_si'],  q=N, labels=LABELS_SI,  duplicates='drop')
df['q_vot'] = pd.qcut(df['perc_vot'], q=N, labels=LABELS_VOT, duplicates='drop')
df['bivar'] = df['q_si'].astype(str) + df['q_vot'].astype(str)
df['color'] = df['bivar'].map(COLORS)

breaks_si  = [df['perc_si'].quantile(q).round(1)  for q in Q_BREAKS]
breaks_vot = [df['perc_vot'].quantile(q).round(1) for q in Q_BREAKS]

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

# ── Legenda N×N come inset ────────────────────────────────────────────────────
legend_ax = fig.add_axes([0.08, 0.10, 0.13, 0.13])
legend_ax.set_aspect('equal')
legend_ax.set_axis_off()

cell = 1.0
for i, col in enumerate(LABELS_SI):
    for j, row in enumerate(LABELS_VOT):
        rect = mpatches.FancyBboxPatch(
            (i * cell, j * cell), cell, cell,
            boxstyle="square,pad=0",
            facecolor=COLORS[col + row],
            edgecolor='white',
            linewidth=0.5,
        )
        legend_ax.add_patch(rect)

legend_ax.set_xlim(-0.1, N + 0.3)
legend_ax.set_ylim(-0.5, N + 0.3)

arrow_kw = dict(arrowstyle='->', color='#333333', lw=1.2)
legend_ax.annotate('', xy=(N + 0.2, -0.15), xytext=(-0.1, -0.15), arrowprops=arrow_kw)
legend_ax.annotate('', xy=(-0.15, N + 0.2), xytext=(-0.15, -0.1), arrowprops=arrow_kw)

legend_ax.text(N / 2, -0.4, '% Sì →', ha='center', va='top',
               fontsize=7.5, color='#333333', fontweight='bold')
legend_ax.text(-0.35, N / 2, '% Affluenza →', ha='right', va='center',
               fontsize=7.5, color='#333333', fontweight='bold', rotation=90)

# ── Titolo e note ─────────────────────────────────────────────────────────────
nomi_classi = {3: 'terzili', 4: 'quartili', 5: 'quintili'}
label_classi = nomi_classi.get(N, f'{N} classi')
titolo = TITOLO or (
    f'Referendum 2026 – Bivariata: % Sì × % Affluenza finale\n'
    f'per comune ({label_classi})'
)
ax.set_title(titolo, fontsize=14, fontweight='bold', pad=16, color='#222222')

si_str  = '  '.join(f'[{breaks_si[k]}–{breaks_si[k+1]}]'  for k in range(N))
vot_str = '  '.join(f'[{breaks_vot[k]}–{breaks_vot[k+1]}]' for k in range(N))
fig.text(0.08, 0.07,
         f"% Sì:        {si_str}\n"
         f"% Affluenza: {vot_str}",
         fontsize=7, color='#555555', family='monospace')

fig.text(0.92, 0.04, 'Fonte: Eligendo / ISTAT', ha='right',
         fontsize=8, color='#888888')

plt.savefig(OUT, dpi=200, bbox_inches='tight', facecolor='white')
print(f"Salvato: {OUT}")
