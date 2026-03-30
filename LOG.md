# LOG

## 2026-03-30

- README: aggiunge Davide Ruffini (Infodata, mappa No/Sì per comune) a chi ha usato i dati

## 2026-03-24

- Aggiunto `mappe/bivariate/bivariate_map.py`: mappa choropleth bivariata % Sì × % Affluenza, N classi configurabile (default quintili), filtro territoriale e palette personalizzabili

## 2026-03-23

- Aggiunto flag `--estero` (off by default) per abilitare download dati estero: `enti_estero.jsonl`, `scrutini_estero.jsonl`, `scrutini_estero_flat.jsonl/csv`, `affluenza_estero.csv`
- Scrutini per singola nazione via `scrutiniFE/.../SK/01/ER/{er}/NA/{na}`; 181 nazioni in ~5s con delay=0 e 4 worker
- Aggiornato `docs/api-reference.md` con endpoint estero (scrutini per nazione/ripartizione, votantiFE, pattern URL)



- Aggiunto retry automatico in `api_get` (2 tentativi, delay 5s) per errori di rete (`ConnectionError`, `Timeout`); i 404 non vengono retrati
- Aggiunto meccanismo resume/append per scrutini `--livello cm`: se `scrutini.jsonl` esiste, legge i `cod` già presenti, salta quelli e fa append dei nuovi; rieseguire lo script completa automaticamente i comuni mancanti


- Aggiunto parametro `--livello [rg|pr|cm]` (default `cm`) per scegliere il livello geografico degli scrutini
  - `rg`: scarica scrutini per 20 regioni → `scrutini_regioni.jsonl` + flat
  - `pr`: scarica scrutini per 110 province → `scrutini_province.jsonl` + flat
  - `cm`: comportamento precedente (7895 comuni + estero) → `scrutini.jsonl` + flat
  - Endpoint verificati live: `scrutiniFI/.../RE/{rg}` e `scrutiniFI/.../RE/{rg}/PR/{pr}`
  - Aggiunti 6 test (flatten regione/provincia, get_scrutini_regione/provincia)
- Aggiunta `lookup/lookup_province_eligendo_istat.csv`: 110 province, mapping deterministico da lookup comuni (no fuzzy)
  - Colonne: `cod_reg`, `cod_prov_eligendo`, `cod_prov_istat`, `regione`, `provincia`
  - Derivato estraendo `cod_eligendo[3:5]` → `cod_prov_eligendo` e `cod_istat[1:3]` → `cod_prov_istat`

## 2026-03-22

- Export `scrutini_flat.csv` generato automaticamente dopo `scrutini_flat.jsonl`
- Aggiunta funzione `jsonl_to_csv` riutilizzabile
- README aggiornato con nuovo file di output e struttura cartella `data`
- Aggiunta licenza CC BY 4.0 (`LICENSE.md`)

## 2026-03-22 (parallelismo scrutini)

- Scrutini comunali ora scaricati in parallelo con `concurrent.futures.ThreadPoolExecutor`
- Nuovo argomento `--workers` (default: 4) per controllare il numero di chiamate parallele
- Rate limiter globale thread-safe: rispetta `--delay` tra una richiesta e la successiva
- Output scritto in ordine originale (raccolta in dict poi scrittura sequenziale)
- Speedup atteso ~4x rispetto alla versione sequenziale

## 2026-03-22 (aggiornamento pomeriggio)

- Scoperto endpoint per affluenza **comunale**: `votantiFI/DE/{data}/TE/09/SK/01/PR/{cod_prov}`
  - Una chiamata per provincia (110 totali) → tutti i comuni con rilevazioni 12:00/19:00/23:00/finale
  - Struttura: `enti.ente_p` = dati provincia, `enti.enti_f` = array comuni con `tipo="COMUNE"` e `com_vot`
  - `cod_eligendo` comune = `cod_reg(2) + cod_prov(3) + f"{cod:04d}"` → compatibile con lookup table
- Prodotta `data/20260322/affluenza.csv`: 7895 comuni × 4 rilevazioni = 31580 righe comunali
  - Colonne: `livello`, `cod_eligendo`, `cod_reg`, `cod_prov`, `denominazione`, `elettori_t`, `rilevazione`, `ora`, `dt_rilevazione`, `sezioni_perv`, `sezioni_tot`, `votanti_t`, `perc_vot`
  - Livelli presenti: nazionale, regione, provincia, comune
- Aggiornato CLI `referendum_download.py`: step 5 scarica automaticamente l'affluenza dopo scrutini

## 2026-03-22

- Testato CLI sul referendum del giorno (20260322): API attiva, affluenza a zero come atteso
- Codici Eligendo ≠ ISTAT: struttura interna `RRPPPCCCC` (9 cifre), regione coincide (01-20) ma prov/comune diversi
- Costruita lookup table `data/lookup_eligendo_istat.csv` (7895 comuni, copertura 100%)
  - Metodo: fuzzy join con `tometo_tomato` su nome regione + nome comune
  - Input Eligendo: `data/20260322/enti.jsonl`
  - Fonte ISTAT: `https://situas-servizi.istat.it/publish/reportspooljson?pfun=61&pdata=01/01/2048`
  - Score min 91 (bilingui Alto Adige/Valle d'Aosta), 7733/7895 con score 100
  - Colonne output: `cod_eligendo`, `nome_eligendo`, `nome_istat`, `regione`, `cod_istat`, `belfiore`, `avg_score`

## 2026-03-14

- Creato PRD in `docs/PRD.md`
- Ispezionato API di eligendo con browser automatizzato
- Scoperto che `elezionistorico.interno.gov.it` e solo HTML (no API JSON)
- Scoperto API JSON su `eleapi.interno.gov.it/siel/PX/`
- Documentato API in `docs/api-reference.md`, `docs/api-discovery-notes.md`, `docs/url-patterns.md`
- Scritto CLI Python `referendum_download.py`
- Aggiunto export flat `scrutini_flat.jsonl` (una riga per comune per quesito)
- Creato `pyproject.toml` per installazione con `uv pip install -e .`
- Testato su 3 comuni + estero: tutto ok
- Init git repo, `.gitattributes`, `.gitignore`, README
