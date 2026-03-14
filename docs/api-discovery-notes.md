# Note di discovery API Eligendo

## Due siti, due architetture

### elezionistorico.interno.gov.it (Archivio Storico)

- Applicazione PHP server-rendered
- **Nessuna API JSON** - tutto e in pagine HTML
- Navigazione via URL con parametri query string
- File JS principale: `eligendo-archivio.js` (solo funzioni di navigazione)
- Dati Open Data disponibili come ZIP (es. `referendum-20220612.zip`)
- URL esempio: `index.php?tpel=F&dtel=12/06/2022&tpa=I&tpe=A&...`

### elezioni.interno.gov.it (Eligendo Live)

- Applicazione Vue.js (SPA)
- **API JSON RESTful** su `eleapi.interno.gov.it`
- API storica su `elestorapi.interno.gov.it` (accesso limitato)
- File JS principali: `vendor.*.js`, `app.*.js`
- URL esempio: `/risultati/20250608/referendum/scrutini/italia/italia`

## Architettura API (da app.js)

### Configurazione tornate

Ogni "tornata" elettorale e configurata nel JS con:

```javascript
{
  data: "20250608",
  titolo: "Amministrative e Referendum",
  isProd: [false, ""],      // se visibile in produzione
  elezioni: [{
    tipo_elez: "referendum",
    fase_elez: "scrutini",   // o "votanti"
    rest_host: "https://eleapi.interno.gov.it"
  }]
}
```

### Prefissi tipo elezione (prfx_elez)

| Codice | Tipo |
|--------|------|
| F | Referendum |
| C | Camera |
| S | Senato |
| E | Europee |
| R | Regionali |
| G | Provinciali/Comunali |

### Prefissi area (prfx_area)

| Codice | Area |
|--------|------|
| I | Italia |
| E | Estero |
| X | In complesso |

### Costruzione URL API

Pattern base dal JS:

```
rest_host + rest_url + azione + prfx_elez + prfx_area + "/DE/" + data_elez + "/TE/" + codi_elez + gerarchia
```

Per referendum Italia:

```
https://eleapi.interno.gov.it/siel/PX/scrutiniFI/DE/20250608/TE/09
```

Per le entita minori (drill-down in una regione):

```
getenti + F + I + Z + /DE/ + data + /TE/ + 09 + /RE/ + codice_regione
```

### codi_elez per tipo

| codi_elez | Tipo |
|-----------|------|
| 01 | Camera |
| 02 | Senato |
| 03 | Europee |
| 07 | Comunali primo turno |
| 08 | Comunali ballottaggio |
| 09 | Referendum |
| 12 | Regionali |

## Limitazioni scoperte

1. `eleapi` serve solo dati delle tornate "attive" (non storiche)
2. `elestorapi` serve dati storici ma blocca l'accesso da curl (403)
3. Le tornate non in produzione (`isProd: false`) non hanno pagina web ma le API funzionano ugualmente
4. I dati Open Data (ZIP) su elezionistorico coprono tutte le date storiche

## Strategia consigliata per il download

Per tornate correnti/recenti:
- Usare `eleapi.interno.gov.it` con le API JSON documentate

Per tornate storiche (es. 2022):
- Opzione A: scaricare lo ZIP da opendata di elezionistorico
- Opzione B: fare scraping delle pagine HTML di elezionistorico
- Opzione C: usare `elestorapi` tramite sessione browser (da verificare)
