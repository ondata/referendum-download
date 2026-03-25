# Mappa bivariata: % Sì × % Affluenza

Mappe choropleth bivariate per comune che incrociano due variabili:

- **Asse X**: % voti Sì sul totale dei voti validi (`perc_si`)
- **Asse Y**: % votanti sul totale degli elettori registrati (`perc_vot`)

## Script disponibili

| Script | Schema colori | Classi | Output |
|--------|--------------|--------|--------|
| `bivariate_map.py` | Trumbo (1981) rosso–viola–blu, legenda a 45° | 3×3 (terzili) | `bivariate_map.png` |
| `bivariate_map_si50.py` | Calda/fredda con soglia semantica al 50% | 4×3 (% Sì con breaks fissi; terzili affluenza) | `bivariate_map_si50.png` |
| `bivariate_map_simone.py` | HSL lightness×hue (corallo→viola→blu) | 3×3 (terzili) | `bivariate_map_simone.png` |

### `bivariate_map.py`

Schema colori Trumbo (1981): interpolazione bilineare tra 4 angoli rosso–viola–blu.
Legenda a quadrato ruotato 45° con frecce sugli assi.

### `bivariate_map_si50.py`

Soglia semantica al 50% per % Sì: classi `<40%`, `40–50%` (No), `50–60%`, `>60%` (Sì).
Palette calda (arancio) per la zona No, fredda (blu) per la zona Sì.
Linea divisoria No/Sì visibile in legenda.

### `bivariate_map_simone.py`

Schema HSL "lightness × hue":
- **hue**: varia con % Sì, da rosso/corallo (+No) → viola (centro) → blu (+Sì)
- **lightness**: varia con l'affluenza, da chiaro (bassa) → scuro (alta)

## Utilizzo

```bash
uv run bivariate_map.py
uv run bivariate_map_si50.py
uv run bivariate_map_simone.py
```

Dipendenze gestite automaticamente via inline metadata PEP 723 (`geopandas`, `pandas`, `matplotlib`, `duckdb`, `numpy`).

## File necessari

| File | Descrizione |
|------|-------------|
| `data/20260322/scrutini_flat.csv` | Scrutini per comune (generato da `referendum_download.py`) |
| `tmp/Com01012026_g_WGS84.geojson` | Confini comunali ISTAT (non versionato, scaricabile da ISTAT) |

## Personalizzazione

Tutte le opzioni si trovano nella sezione **CONFIG** di ciascuno script.

### Filtro territoriale

Per produrre una mappa di una sola regione, imposta entrambi i filtri:

```python
FILTRO_GEOJSON  = "COD_REG == 19"   # Sicilia (campo GeoJSON ISTAT)
FILTRO_SCRUTINI = "cod_reg = '19'"  # Sicilia (SQL WHERE, senza AND iniziale)
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

### Titolo personalizzato

```python
TITOLO = "Il mio titolo personalizzato"  # None = generato automaticamente
```
