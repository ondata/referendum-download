# API Reference - Eligendo Referendum

## Base URL

```
https://eleapi.interno.gov.it/siel/PX/
```

Per i dati storici (non ancora verificato accesso diretto):

```
https://elestorapi.interno.gov.it/retrospettivo/
```

## Headers richiesti

```http
Origin: https://elezioni.interno.gov.it
Referer: https://elezioni.interno.gov.it/
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36
```

Senza `User-Agent` e `Origin` appropriati si riceve un 403.

## Parametri URL

| Parametro | Significato | Valori per referendum |
|-----------|-------------|----------------------|
| `F` | prfx_elez (tipo elezione) | F = Referendum |
| `I` | prfx_area (Italia) | I = Italia, E = Estero |
| `DE` | Data elezione | Formato YYYYMMDD (es. `20250608`) |
| `TE` | Tipo elezione (codi_elez) | `09` per referendum |
| `RE` | Regione | Codice 2 cifre (es. `01` = Piemonte) |
| `PR` | Provincia | Codice 3 cifre (es. `002` = Alessandria) |
| `CM` | Comune | Codice 4 cifre (es. `0010` = Acqui Terme) |
| `SK` | Scheda (per votanti) | Numero quesito (es. `01`) |

## Endpoint

### 1. getentiFI - Lista entita territoriali

Restituisce TUTTE le entita (regioni, province, comuni) in un'unica chiamata.

```
GET /siel/PX/getentiFI/DE/{data}/TE/09
```

**Risposta:**

```json
{
  "int": {
    "file": "GEOPOLITICA REFERENDUM",
    "area": "I",
    "t_ele": "Referendum",
    "dt_ele": 20250608000000
  },
  "enti": [
    {
      "cod": "010000000",
      "desc": "PIEMONTE",
      "tipo": "RE",
      "tipo_comune": null,
      "dt_agg": 20250612121222,
      "tipo_tras": null
    },
    {
      "cod": "010020000",
      "desc": "ALESSANDRIA",
      "tipo": "PR",
      "tipo_comune": null,
      "dt_agg": 20250612121222,
      "tipo_tras": null
    },
    {
      "cod": "010020010",
      "desc": "ACQUI TERME",
      "tipo": "CM",
      "tipo_comune": "M",
      "dt_agg": 20250609192534,
      "tipo_tras": "CO"
    }
  ]
}
```

**Struttura codice entita (`cod`):**

- `RRPPPCCCC` (9 cifre)
- `RR` = codice regione (01-20)
- `PPP` = codice provincia (000 per regione)
- `CCCC` = codice comune (0000 per regione/provincia)

**Tipi entita (`tipo`):**

| tipo | Significato | Conteggio (2025) |
|------|-------------|------------------|
| RE | Regione | 20 |
| PR | Provincia | 106 |
| CM | Comune | 7896 |

### 2. getentiFE - Lista entita Estero

```
GET /siel/PX/getentiFE/DE/{data}/TE/09
```

Stessa struttura di getentiFI, per le circoscrizioni estero.

### 3. scrutiniFI - Risultati scrutini Italia

**Livello nazionale:**

```
GET /siel/PX/scrutiniFI/DE/{data}/TE/09
```

**Livello regionale:**

```
GET /siel/PX/scrutiniFI/DE/{data}/TE/09/RE/{codice_regione}
```

**Livello provinciale:**

```
GET /siel/PX/scrutiniFI/DE/{data}/TE/09/RE/{codice_regione}/PR/{codice_provincia}
```

**Livello comunale:**

```
GET /siel/PX/scrutiniFI/DE/{data}/TE/09/RE/{codice_regione}/PR/{codice_provincia}/CM/{codice_comune}
```

**Risposta (livello nazionale):**

```json
{
  "int": {
    "st": "ESERCIZIO",
    "t_ele": "Referendum",
    "t_ref": "ABROGATIVO",
    "f_elet": "SCRUTINI",
    "dt_ele": 20250608000000,
    "l_terr": "ITALIA",
    "area": "I",
    "ele_m": 22246208,
    "ele_f": 23751733,
    "ele_t": 45997941,
    "sz_tot": 61591
  },
  "note": null,
  "scheda": [
    {
      "cod": 1,
      "desc": null,
      "sz_perv": 61591,
      "vot_m": 6549441,
      "vot_f": 7517814,
      "vot_t": 14067255,
      "perc_vot": "30,58",
      "sk_bianche": 221715,
      "sk_nulle": 91365,
      "sk_contestate": 229,
      "voti_si": 12249614,
      "voti_no": 1504332,
      "perc_si": "89,06",
      "perc_no": "10,94",
      "dt_agg": 20250611100054
    }
  ]
}
```

**Campi int (intestazione):**

| Campo | Significato |
|-------|-------------|
| st | Stato (ESERCIZIO) |
| t_ele | Tipo elezione |
| t_ref | Tipo referendum (ABROGATIVO) |
| f_elet | Fase (SCRUTINI) |
| dt_ele | Data elezione |
| l_terr | Livello territoriale (ITALIA/REGIONE/PROVINCIA/COMUNE) |
| area | I = Italia, E = Estero |
| ele_m/ele_f/ele_t | Elettori maschi/femmine/totale |
| sz_tot | Sezioni totali |
| cod_reg/desc_reg | Codice/descrizione regione (se livello <= regione) |
| cod_prov/desc_prov | Codice/descrizione provincia (se livello <= provincia) |
| cod_com/desc_com | Codice/descrizione comune (se livello = comune) |
| tipo_tras | Tipo trasmissione (CO=completo, SZ=per sezione) |

**Campi scheda (un elemento per ogni quesito referendario):**

| Campo | Significato |
|-------|-------------|
| cod | Numero quesito (1, 2, 3, ...) |
| desc | Descrizione quesito (spesso null, nel testo della pagina) |
| sz_perv | Sezioni pervenute |
| vot_m/vot_f/vot_t | Votanti maschi/femmine/totale |
| perc_vot | Percentuale votanti |
| sk_bianche | Schede bianche |
| sk_nulle | Schede nulle |
| sk_contestate | Schede contestate |
| voti_si | Voti SI |
| voti_no | Voti NO |
| perc_si | Percentuale SI |
| perc_no | Percentuale NO |
| dt_agg | Data ultimo aggiornamento |

### 4. scrutiniFE - Risultati scrutini Estero

```
GET /siel/PX/scrutiniFE/DE/{data}/TE/09
```

Stessa struttura di scrutiniFI, per le circoscrizioni estero. Campi votanti leggermente diversi (solo `vot_t`, senza `vot_m`/`vot_f`).

### 5. votantiFI - Dati affluenza

```
GET /siel/PX/votantiFI/DE/{data}/TE/09/SK/{codice_scheda}
```

Restituisce dati affluenza dettagliati per una specifica scheda.

## Date referendum disponibili (confermate API)

| Data | Referendum |
|------|-----------|
| 20250608 | Referendum abrogativi 2025 (5 quesiti) |

Le date storiche (es. 20220612) danno errore "Data non permessa" su `eleapi`. Il sito `elestorapi.interno.gov.it` serve i dati storici ma richiede autenticazione/sessione browser.

## Derivazione codici dalla gerarchia entita

Da `getentiFI` il codice a 9 cifre si decompone:

```
010020010 -> RE=01, PR=002, CM=0010
         RR PPP CCCC
```

Per le chiamate API:
- `/RE/01` (2 cifre - regione)
- `/PR/002` (3 cifre - provincia)
- `/CM/0010` (4 cifre - comune)

## Errori comuni

```json
{"Error": {"desc": "Data non permessa"}}
{"Error": {"id": "200", "desc": "Dati non trovati", "value": "..."}}
{"Error": {"id": "310", "desc": "Errore di sintassi", "value": "..."}}
```

## Note

- L'endpoint `getentiFI` restituisce TUTTE le entita (8000+ record) in una sola chiamata
- I dati di scrutinio sono disponibili a tutti i livelli: nazionale, regionale, provinciale, comunale
- Ogni risposta scrutini contiene un array `scheda` con un elemento per ciascun quesito referendario
- La data nell'URL e in formato YYYYMMDD senza separatori
