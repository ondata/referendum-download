# referendum-download

CLI Python per scaricare i dati dei referendum italiani da [Eligendo](https://elezioni.interno.gov.it) (`eleapi.interno.gov.it`) in formato JSONLines.

Scarica scrutini e affluenza a livello comunale per tutti i comuni italiani, più i dati dell'estero.

## Requisiti

- Python >= 3.9
- [uv](https://docs.astral.sh/uv/) (consigliato) oppure pip

## Installazione

```bash
git clone https://github.com/aborruso/referendum-download.git
cd referendum-download
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

## Uso

```bash
# Scarica tutti i dati
referendum-download 20260322

# Oppure passa l'URL completo
referendum-download https://elezioni.interno.gov.it/risultati/20260322/referendum/scrutini/italia/italia

# Solo affluenza (es. aggiornamento alle 19:00)
referendum-download --solo-affluenza --force 20260322

# Solo scrutini (es. dopo chiusura seggi)
referendum-download --solo-scrutini --force 20260322

# Test con pochi comuni
referendum-download --solo-scrutini --limit 10 --delay 0.3 20260322
```

In alternativa, con `uv run` senza attivare il venv:

```bash
uv run referendum-download 20260322
```

### Opzioni

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--output-dir` | `data` | Directory di output |
| `--delay` | `1.0` | Pausa in secondi tra le chiamate API |
| `--limit` | `0` | Numero massimo di comuni (0 = tutti) |
| `--force` | off | Forza re-download anche se i file esistono già |
| `--solo-scrutini` | off | Scarica solo gli scrutini, salta affluenza |
| `--solo-affluenza` | off | Scarica solo l'affluenza, salta scrutini |
| `--workers` | `4` | Chiamate parallele per gli scrutini |

## Struttura della cartella `data`

```
data/
├── {YYYYMMDD}/          # una sottocartella per tornata elettorale
│   ├── enti.jsonl
│   ├── scrutini.jsonl
│   ├── scrutini_flat.jsonl
│   ├── scrutini_flat.csv
│   └── affluenza.csv
└── lookup_eligendo_istat.csv   # copia della lookup (generata da lookup/)
```

Ogni tornata è identificata dalla data nel formato `YYYYMMDD` (es. `20260322`).

## Output

I file vengono salvati in `data/{YYYYMMDD}/`:

| File | Descrizione |
|------|-------------|
| `enti.jsonl` | Lista completa delle entità territoriali (regioni, province, comuni) |
| `scrutini.jsonl` | Dati raw degli scrutini (un record JSON per comune + estero) |
| `scrutini_flat.jsonl` | Dati appiattiti: una riga per comune per quesito referendario |
| `scrutini_flat.csv` | Stesso contenuto di `scrutini_flat.jsonl` in formato CSV |
| `affluenza.csv` | Affluenza per comune alle 4 rilevazioni (12:00, 19:00, 23:00, finale) |

### Struttura `scrutini_flat.jsonl`

Ogni riga contiene:

```
cod, cod_istat, area, livello, cod_reg, cod_prov, cod_com,
desc_com, desc_prov, desc_reg,
elettori_m, elettori_f, elettori_t, sezioni_tot,
quesito_cod, sezioni_perv,
votanti_m, votanti_f, votanti_t, perc_vot,
sk_bianche, sk_nulle, sk_contestate,
voti_si, voti_no, perc_si, perc_no
```

`cod_istat` è il codice ISTAT a 6 cifre del comune (es. `015146`), ricavato dalla lookup table `lookup/lookup_eligendo_istat.csv`.

### Struttura `affluenza.csv`

Una riga per entità (nazionale / regione / provincia / comune) per ogni rilevazione:

```
livello, cod_eligendo, cod_istat, cod_reg, cod_prov,
denominazione, elettori_t,
rilevazione, ora, dt_rilevazione,
sezioni_perv, sezioni_tot, votanti_t, perc_vot
```

L'affluenza per comune usa 1 chiamata API per provincia (110 totali), non per comune.

### Esplorare i dati

Con **DuckDB**:

```bash
# Affluenza ore 12:00 per comune
duckdb -c "
SELECT cod_istat, denominazione, perc_vot
FROM read_csv('data/20260322/affluenza.csv')
WHERE livello = 'comune' AND ora = '12:00'
ORDER BY CAST(REPLACE(perc_vot, ',', '.') AS DOUBLE) DESC
LIMIT 20
"

# Scrutini per comune (dopo lo spoglio)
duckdb -c "
SELECT cod_istat, desc_com, desc_reg, elettori_t, votanti_t, perc_vot, voti_si, voti_no, perc_si
FROM read_json_auto('data/20260322/scrutini_flat.jsonl')
WHERE quesito_cod = 1
ORDER BY desc_reg, desc_com
LIMIT 20
"
```

## Lookup Eligendo → ISTAT

I codici comunali di Eligendo (formato interno `RRPPPCCCC` a 9 cifre) non coincidono con i codici ISTAT. La tabella `lookup/lookup_eligendo_istat.csv` mappa i due sistemi.

### Come è stata generata

Lo script `lookup/generate_lookup.sh` esegue questi passi:

1. **Scarica gli enti Eligendo** dall'API (`getentiFI`) e filtra i soli comuni (`tipo=CM`)
2. **Scarica i comuni ISTAT** dall'API SITUAS (`pfun=61`) con nomi, codici e belfiore
3. **Normalizza entrambi i lati** per il join:
   - rimuove apostrofi (Eligendo usa `FORLI'` per `FORLÌ`, `DE'` per `de'`)
   - converte trattini in spazi (`GIARDINI-NAXOS` → `GIARDINI NAXOS`)
   - usa `COMUNE_IT` ISTAT (nome solo italiano, senza minoranze linguistiche)
   - usa solo la parte italiana del nome Eligendo per i comuni bilingui (prima del `/`)
4. **Fuzzy join** con [`tometo_tomato`](https://github.com/aborruso/tometo_tomato) su `(regione, comune)`:
   - `--block-prefix 2` limita i confronti a comuni con stesso prefisso a 2 caratteri nella stessa regione
   - `--latinize` normalizza gli accenti prima del confronto
   - threshold default (85/100)
5. **Deduplicazione**: se due codici Eligendo matchano lo stesso cod_istat, vince quello con score più alto; l'altro riceve NULL
6. **Override manuali** per comuni fusi non risolvibili automaticamente (CASTEGNERO e NANTO → `Castegnero Nanto`, cod `024129`)

### Uso

```bash
# Genera/aggiorna la lookup (richiede: duckdb, tometo_tomato)
bash lookup/generate_lookup.sh

# Oppure usa un file enti.jsonl già scaricato
bash lookup/generate_lookup.sh data/20260322/enti.jsonl
```

Output: `lookup/lookup_eligendo_istat.csv` con colonne `cod_eligendo`, `nome_eligendo`, `nome_istat`, `regione`, `cod_istat`, `belfiore`, `match_score`.

Copertura: 7895/7895 comuni (100%). Score minimo: 90.0.

## Idempotenza

Ogni file viene saltato se già presente. Per forzare il re-download:

```bash
referendum-download --force 20260322           # tutto
referendum-download --force --solo-affluenza 20260322  # solo affluenza
```

## Note

- L'API `eleapi.interno.gov.it` serve solo tornate recenti/attive, non dati storici
- I dati storici sono disponibili come ZIP su [elezionistorico.interno.gov.it](https://elezionistorico.interno.gov.it/eligendo/opendata.php)
- Con ~7900 comuni e delay 1s, il download scrutini richiede circa 2 ore
- Con delay 0.3s e 110 province, il download affluenza richiede circa 40 secondi
