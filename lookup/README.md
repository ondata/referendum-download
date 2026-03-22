# Lookup Eligendo → ISTAT

Tabella di mapping tra i codici interni del Ministero dell'Interno (sistema **Eligendo**) e i codici **ISTAT** dei comuni italiani.

## Il problema

L'API di Eligendo (`eleapi.interno.gov.it`) identifica ogni comune con un codice proprietario a 9 cifre (`RRPPPCCCC`):

| Parte | Cifre | Esempio | Significato |
|-------|-------|---------|-------------|
| `RR` | 01–20 | `01` | Regione (coincide con ISTAT) |
| `PPP` | 3 | `002` | Provincia (numerazione interna) |
| `CCCC` | 4 | `0010` | Comune (numerazione interna) |

Questo codice **non corrisponde al codice ISTAT** (`PPP` e `CCCC` usano numerazioni diverse). Per esempio, Alessandria ha provincia `002` in Eligendo ma `006` in ISTAT.

Senza un mapping esplicito è impossibile unire i dati elettorali di Eligendo con qualsiasi altra fonte territoriale (dati demografici, geografici, amministrativi) che usi il codice ISTAT.

## La soluzione: fuzzy join per nome

Il solo campo disponibile in entrambi i sistemi per la riconciliazione è il **nome del comune**. Il codice regione (`RR`) coincide invece esattamente, quindi si usa come blocco.

La strategia è:

1. Scaricare l'elenco enti da Eligendo (nome + codice interno)
2. Scaricare l'elenco comuni ISTAT con nome ufficiale e codice ISTAT
3. Fare un **fuzzy join** su `(regione, comune)` per gestire le differenze tipografiche tra i due dataset

### Perché serve il fuzzy join

I nomi non sono identici tra i due sistemi:

| Caso | Eligendo | ISTAT |
|------|----------|-------|
| Accenti con apostrofo | `TRINITE'` | `Trinité` |
| Carattere ß | `WEINSTRASSE` | `Weinstraße` |
| Nomi bilingue (Alto Adige, FVG) | `SAN FLORIANO DEL COLLIO` | `San Floriano del Collio-Števerjan` |
| Solo maiuscole | `ACQUI TERME` | `Acqui Terme` |

ISTAT fornisce però anche il campo `COMUNE_IT` con il **solo nome italiano**, senza la parte nella lingua minoritaria. Il join usa `COMUNE_IT` invece di `COMUNE` per massimizzare i punteggi di similarità sui comuni bilingue. Il `nome_istat` nell'output riporta invece `COMUNE` (nome completo ufficiale).

Un join esatto fallisce su questi casi. Un join fuzzy li gestisce tutti con score ≥ 91.

### tometo_tomato

[`tometo_tomato`](https://github.com/aborruso/tometo_tomato) è uno strumento di **fuzzy join** basato su DuckDB. Confronta stringhe con algoritmi di similarità (es. `token_set_ratio`) e produce:

- un file **matched**: record con un solo match sopra la soglia
- un file **ambiguous**: record con più candidati simili (da verificare)

Per questo caso si usano due opzioni chiave:

- `--block-prefix 20` — prima di calcolare la similarità, raggruppa i record che condividono gli stessi primi 20 caratteri di `regione|comune`. Poiché il nome regione è identico nei due dataset, questo riduce il confronto da 7895 × 7895 combinazioni a ~400 per regione, rendendo il processo veloce.
- `--latinize` — normalizza i caratteri accentati prima del confronto (`é→e`, `ß→ss`, ecc.), aumentando il punteggio di similarità per i casi con differenze solo tipografiche.

## Output

File: `lookup_eligendo_istat.csv`

| Colonna | Descrizione | Esempio |
|---------|-------------|---------|
| `cod_eligendo` | Codice interno Eligendo (9 cifre) | `010020010` |
| `nome_eligendo` | Nome comune in Eligendo (maiuscolo) | `ACQUI TERME` |
| `nome_istat` | Nome ufficiale ISTAT | `Acqui Terme` |
| `regione` | Nome regione | `Piemonte` |
| `cod_istat` | Codice ISTAT comune (6 cifre) | `006001` |
| `belfiore` | Codice catastale (Belfiore) | `A052` |
| `match_score` | Qualità del match (0–100) | `100.0` |

### Qualità del matching (su dati referendum 2026-03-22)

- **7895 comuni** mappati su 7895 (copertura 100%)
- **7733** con score 100 (nome identico dopo normalizzazione)
- **162** con score 91–99 (differenze tipografiche — tutti corretti)
- **Score minimo: 91** (San Floriano del Collio, nome sloveno aggiunto in ISTAT)

## Utilizzo

```bash
# Con file enti già scaricato
bash generate_lookup.sh ../data/20260322/enti.jsonl

# Scarica enti dalla data odierna e genera il mapping
bash generate_lookup.sh
```

### Dipendenze

```bash
pip install tometo_tomato   # https://github.com/aborruso/tometo_tomato
# duckdb, curl, python3 già presenti nel sistema
```

## Fonti

- **Eligendo API**: `https://eleapi.interno.gov.it/siel/PX/getentiFI/DE/{data}/TE/09`
- **ISTAT comuni**: `https://situas-servizi.istat.it/publish/reportspooljson?pfun=61&pdata=01/01/2048`
