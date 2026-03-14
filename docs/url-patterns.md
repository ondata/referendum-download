# URL Patterns - elezionistorico.interno.gov.it

## Struttura URL navigazione

La navigazione su elezionistorico avviene via parametri query string su `index.php`.

### Parametri principali

| Parametro | Significato | Valori |
|-----------|-------------|--------|
| tpel | Tipo elezione | F=Referendum, C=Camera, S=Senato, E=Europee, R=Regionali |
| dtel | Data elezione | DD/MM/YYYY (es. 12/06/2022) |
| tpa | Area | I=Italia, E=Estero, Y=Italia+Estero |
| tpe | Tipo ente | A=Aggregato, R=Regione, P=Provincia, C=Comune |
| ms | Mostra schede | S=Si, N=No |
| ne1 | Codice regione | Numerico (es. 1=Piemonte) |
| ne2 | Codice provincia | Numerico (es. 81=Torino) |
| ne3 | Codice comune | Numerico composto (es. 810010) |
| lev0-3 | Livello gerarchico | Numerico |
| levsut0-3 | Sotto-livello | Numerico |
| es0-3 | Espansione | S/N |

### Esempi URL per livelli

**Livello nazionale (Italia):**

```
index.php?tpel=F&dtel=12/06/2022&es0=S&tpa=I&lev0=0&levsut0=0&ms=S&tpe=A
```

**Livello regionale (Piemonte):**

```
index.php?tpel=F&dtel=12/06/2022&tpa=I&tpe=R&lev0=0&levsut0=0&levsut1=1&es0=S&es1=S&ms=S&ne1=1&lev1=1
```

**Livello provinciale (Torino):**

```
index.php?tpel=F&dtel=12/06/2022&tpa=I&tpe=P&lev0=0&levsut0=0&lev1=1&levsut1=1&levsut2=2&ne1=1&es0=S&es1=S&es2=S&ms=S&ne2=81&lev2=81
```

**Livello comunale (Aglie):**

```
index.php?tpel=F&dtel=12/06/2022&tpa=I&tpe=C&lev0=0&levsut0=0&lev1=1&levsut1=1&lev2=81&levsut2=2&levsut3=3&ne1=1&ne2=81&es0=S&es1=S&es2=S&es3=N&ms=S&ne3=810010&lev3=10
```

### Gerarchia select (combo box)

I combo box usano `onchange` con `carica_pagina()`:

**Area:**

```javascript
// value format: "I-lev00-levsut00-msS-tpeA"
carica_pagina('index.php?tpel=F&dtel=12/06/2022&es0=S', 'tpa', value);
```

**Regione:**

```javascript
// value format: "1-lev11" (codice_regione + "-lev1" + codice_regione)
carica_pagina('index.php?tpel=F&dtel=12/06/2022&tpa=I&tpe=R&...', 'ne1', value);
```

**Provincia:**

```javascript
// value format: "81-lev281" (codice_provincia + "-lev2" + codice_provincia)
carica_pagina('index.php?tpel=F&dtel=12/06/2022&tpa=I&tpe=P&...', 'ne2', value);
```

**Comune:**

```javascript
// value format: "810010-lev310" (codice_comune + "-lev3" + codice)
carica_pagina('index.php?tpel=F&dtel=12/06/2022&tpa=I&tpe=C&...', 'ne3', value);
```

### Struttura dati HTML

Le tabelle dati usano classi CSS:
- `dati_riepilogo` - tabelle affluenza e schede
- `dati` - tabelle risultati SI/NO

Per ogni quesito referendario c'e un blocco con:
1. Titolo del quesito (in un div colorato)
2. Tabella affluenza: Votanti, %
3. Tabella schede: Valide, Bianche, Non valide
4. Tabella risultati: SI (voti, %), NO (voti, %)

### Date referendum disponibili

Da combo "Scegli Data" (formato DD/MM/YYYY):

- 08/06/2025
- 12/06/2022
- 20/09/2020
- 04/12/2016
- 17/04/2016
- 12/06/2011
- 21/06/2009
- 25/06/2006
- 12/06/2005
- 15/06/2003
- 07/10/2001
- 21/05/2000
- 18/04/1999
- 15/06/1997
- 11/06/1995
- 18/04/1993
- 09/06/1991
- 03/06/1990
- 18/06/1989
- 08/11/1987
- 09/06/1985
- 17/05/1981
- 11/06/1978
- 12/05/1974
- 02/06/1946

### Open Data ZIP

Disponibili su `elezionistorico.interno.gov.it/eligendo/opendata.php`:

```
referendum-20220612.zip
```
