# Mappa bivariata: % Sì × % Affluenza

Mappa choropleth bivariata per comune che incrocia due variabili:

- **Asse X**: % voti Sì sul totale dei voti validi (`perc_si`)
- **Asse Y**: % votanti sul totale degli elettori registrati (`perc_vot`)

La palette è generata per interpolazione bilineare tra 4 colori angolari (ispirata allo schema Stevens teal × pink/violet).

## Requisiti

```bash
uv run bivariate_map.py
```

Dipendenze gestite automaticamente via inline metadata PEP 723 (`geopandas`, `pandas`, `matplotlib`, `duckdb`, `numpy`).

### File necessari

| File | Descrizione |
|------|-------------|
| `data/20260322/scrutini_flat.csv` | Scrutini per comune (generato da `referendum_download.py`) |
| `tmp/Com01012026_g_WGS84.geojson` | Confini comunali ISTAT (non versionato, scaricabile da ISTAT) |

## Personalizzazione

Tutte le opzioni si trovano nella sezione **CONFIG** all'inizio dello script.

### Numero di classi

```python
N = 5   # quintili (default)
N = 4   # quartili
N = 3   # terzili
```

### Filtro territoriale

Per produrre una mappa di una sola regione, imposta entrambi i filtri:

```python
# Filtra il GeoJSON (usa i campi del file ISTAT)
FILTRO_GEOJSON = "COD_REG == 19"   # Sicilia

# Filtra i dati scrutini (SQL WHERE clause, senza AND iniziale)
FILTRO_SCRUTINI = "cod_reg = '19'"
```

Codici regione ISTAT:

| Codice | Regione | Codice | Regione |
|--------|---------|--------|---------|
| 1 | Piemonte | 11 | Marche |
| 2 | Valle d'Aosta | 12 | Lazio |
| 3 | Lombardia | 13 | Abruzzo |
| 4 | Trentino-Alto Adige | 14 | Molise |
| 5 | Veneto | 15 | Campania |
| 6 | Friuli-Venezia Giulia | 16 | Puglia |
| 7 | Liguria | 17 | Basilicata |
| 8 | Emilia-Romagna | 18 | Calabria |
| 9 | Toscana | 19 | Sicilia |
| 10 | Umbria | 20 | Sardegna |

### Palette colori

Modifica i 4 angoli della griglia (valori RGB):

```python
C00  = np.array([232, 232, 232])  # si_basso × vot_basso  → grigio chiaro
C_N0 = np.array([90,  200, 200])  # si_alto  × vot_basso  → teal
C0_N = np.array([190, 100, 172])  # si_basso × vot_alto   → viola/rosa
C_NN = np.array([59,   73, 148])  # si_alto  × vot_alto   → blu scuro
```

Tutti i 25 (o 9/16) colori intermedi vengono calcolati automaticamente per interpolazione.

### Titolo personalizzato

```python
TITOLO = "Il mio titolo personalizzato"
```

Se `None`, il titolo viene generato automaticamente con il numero di classi.

### File di output

```python
OUT = pathlib.Path(__file__).parent / "bivariate_map.png"
```

Il file viene salvato nella stessa directory dello script. Cambia il percorso se necessario.
