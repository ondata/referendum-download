# referendum-download

CLI Python per scaricare i dati dei referendum italiani da [Eligendo](https://elezioni.interno.gov.it) (`eleapi.interno.gov.it`) in formato JSONLines.

Scarica i risultati degli scrutini a livello comunale per tutti i comuni italiani, più i dati dell'estero.

## Requisiti

- Python >= 3.9
- [uv](https://docs.astral.sh/uv/) (consigliato) oppure pip

## Installazione

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

## Uso

```bash
# Scarica tutti i dati del referendum 2025
referendum-download 20250608

# Oppure passa l'URL completo
referendum-download https://elezioni.interno.gov.it/risultati/20250608/referendum/scrutini/italia/italia

# Test con pochi comuni
referendum-download --limit 10 --delay 0.5 20250608

# Cambia directory di output
referendum-download --output-dir output 20250608
```

### Opzioni

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--output-dir` | `data` | Directory di output |
| `--delay` | `1.0` | Pausa in secondi tra le chiamate API |
| `--limit` | `0` | Numero massimo di comuni (0 = tutti) |

## Output

I file vengono salvati in `data/{YYYYMMDD}/`:

| File | Descrizione |
|------|-------------|
| `enti.jsonl` | Lista completa delle entita territoriali (regioni, province, comuni) |
| `scrutini.jsonl` | Dati raw degli scrutini (un record JSON per comune + estero) |
| `scrutini_flat.jsonl` | Dati appiattiti: una riga per comune per quesito referendario |

### Struttura `scrutini_flat.jsonl`

Ogni riga contiene:

```
cod, area, livello, cod_reg, cod_prov, cod_com,
desc_com, desc_prov, desc_reg,
elettori_m, elettori_f, elettori_t, sezioni_tot,
quesito_cod, sezioni_perv,
votanti_m, votanti_f, votanti_t, perc_vot,
sk_bianche, sk_nulle, sk_contestate,
voti_si, voti_no, perc_si, perc_no
```

### Esplorare i dati

Con **jq**:

```bash
# Sommario per comune
jq -c '{cod, desc_com, quesito_cod, voti_si, voti_no, perc_si}' data/20250608/scrutini_flat.jsonl | head

# Solo quesito 1
jq -c 'select(.quesito_cod == 1) | {desc_com, voti_si, voti_no, perc_si}' data/20250608/scrutini_flat.jsonl
```

Con **DuckDB**:

```bash
duckdb -c "
SELECT desc_reg, desc_prov, desc_com, quesito_cod, elettori_t, votanti_t, perc_vot, voti_si, voti_no
FROM read_json_auto('data/20250608/scrutini_flat.jsonl')
WHERE quesito_cod = 1
ORDER BY desc_reg, desc_prov, desc_com
LIMIT 20
"
```

## Idempotenza

Se `scrutini.jsonl` esiste gia, lo script non riscarica i dati. Per forzare il riscaricare, cancella il file o la cartella.

## Note

- L'API `eleapi.interno.gov.it` serve solo tornate recenti/attive, non dati storici
- I dati storici (es. referendum 2022) sono disponibili come ZIP su [elezionistorico.interno.gov.it](https://elezionistorico.interno.gov.it/eligendo/opendata.php)
- Con ~7900 comuni e 1 secondo di pausa, il download completo richiede circa 2 ore e mezza
