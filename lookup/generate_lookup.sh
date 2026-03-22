#!/usr/bin/env bash
# Genera la tabella di mapping tra codici Eligendo (Ministero Interno) e codici ISTAT.
#
# Output: lookup_eligendo_istat.csv
#
# Dipendenze: curl, python3, duckdb, tometo_tomato
# Installazione tometo_tomato: pip install tometo_tomato
#
# Uso:
#   bash generate_lookup.sh [enti.jsonl]
#
# Se non si passa il file enti.jsonl, viene scaricato dall'API Eligendo
# usando la data odierna. Alternativamente si può passare qualsiasi file
# enti.jsonl già scaricato (es. data/20260322/enti.jsonl).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMPDIR_WORK=$(mktemp -d)
trap 'rm -rf "$TMPDIR_WORK"' EXIT

ISTAT_URL="https://situas-servizi.istat.it/publish/reportspooljson?pfun=61&pdata=01/01/2048"
ELIGENDO_API="https://eleapi.interno.gov.it/siel/PX/getentiFI/DE"
OUTPUT="${SCRIPT_DIR}/lookup_eligendo_istat.csv"

# --- 1. File enti Eligendo ---

ENTI_FILE="${1:-}"

if [[ -z "$ENTI_FILE" ]]; then
    DATA_ELEZ=$(date +%Y%m%d)
    echo "Scarico enti Eligendo per data ${DATA_ELEZ}..."
    curl -s \
        -H "Origin: https://elezioni.interno.gov.it" \
        -H "Referer: https://elezioni.interno.gov.it/" \
        -H "User-Agent: Mozilla/5.0" \
        "${ELIGENDO_API}/${DATA_ELEZ}/TE/09" \
        | python3 -c "
import sys, json
d = json.load(sys.stdin)
for e in d['enti']:
    print(json.dumps(e, ensure_ascii=False))
" > "${TMPDIR_WORK}/enti.jsonl"
    ENTI_FILE="${TMPDIR_WORK}/enti.jsonl"
    echo "  OK: $(grep -c . "${ENTI_FILE}") entità"
else
    echo "Uso file enti: ${ENTI_FILE}"
fi

# --- 2. Dati ISTAT ---

echo "Scarico dati ISTAT..."
curl -s "${ISTAT_URL}" \
    | python3 -c "
import sys, json, csv
d = json.load(sys.stdin)['resultset']
fields = ['COD_REG', 'DEN_REG', 'PRO_COM_T', 'COMUNE', 'COMUNE_IT', 'DEN_UTS', 'COD_CATASTO']
w = csv.DictWriter(sys.stdout, fieldnames=fields, lineterminator='\n')
w.writeheader()
for r in d:
    w.writerow({k: r[k] for k in fields})
" > "${TMPDIR_WORK}/istat.csv"
echo "  OK: $(wc -l < "${TMPDIR_WORK}/istat.csv") comuni ISTAT"

# --- 3. Prepara CSV Eligendo con nome regione ---
# Il codice Eligendo è RRPPPCCCC (9 cifre): RR=regione, PPP=provincia, CCCC=comune.
# Il codice regione (RR) coincide con il COD_REG ISTAT (01-20), quindi si usa
# per agganciare il nome regione e ridurre lo spazio di ricerca nel fuzzy join.
#
# Alcuni comuni in Eligendo usano già il nome bilingue (es. "TRODENA NEL PARCO
# NATURALE/TRUDEN IM NATURPARK"). Per il join usiamo solo la parte italiana
# (prima del '/'), mentre il nome completo originale resta in comune_originale.

echo "Preparo CSV Eligendo..."
duckdb -c "
COPY (
  SELECT
    e.cod AS cod_eligendo,
    e.cod[1:2] AS cod_reg,
    i.DEN_REG AS regione,
    e.\"desc\" AS comune_originale,
    trim(regexp_replace(regexp_replace(split_part(e.\"desc\", '/', 1), '''', '', 'g'), '[-]+', ' ', 'g')) AS comune
  FROM read_ndjson_auto('${ENTI_FILE}') e
  JOIN (SELECT DISTINCT COD_REG, DEN_REG FROM read_csv('${TMPDIR_WORK}/istat.csv', auto_detect=true)) i
    ON e.cod[1:2] = i.COD_REG
  WHERE e.tipo = 'CM'
) TO '${TMPDIR_WORK}/eligendo.csv' (HEADER, DELIMITER ',');
"
echo "  OK: $(wc -l < "${TMPDIR_WORK}/eligendo.csv") comuni Eligendo"

# --- 3b. Crea versione normalizzata ISTAT con apostrofi rimossi ---
# Necessario per far coincidere i nomi: Eligendo usa ' come sostituto dell'accento
# (FORLI' = FORLÌ) e come apostrofo vero (DE', NE'). ISTAT usa la lettera accentata
# o l'apostrofo Unicode. Rimuovendo tutti gli apostrofi da entrambi i lati si
# ottiene una forma normalizzata coerente per il fuzzy join.

echo "Normalizzo ISTAT per il join..."
duckdb -c "
COPY (
  SELECT *, trim(regexp_replace(regexp_replace(COMUNE_IT, '''', '', 'g'), '[-]+', ' ', 'g')) AS COMUNE_IT_NORM
  FROM read_csv('${TMPDIR_WORK}/istat.csv', auto_detect=true)
) TO '${TMPDIR_WORK}/istat_norm.csv' (HEADER, DELIMITER ',');
"

# --- 4. Fuzzy join con tometo_tomato ---
# Join su (regione, comune): la regione è identica nei due dataset (blocca la ricerca),
# il comune è fuzzy per gestire differenze tipografiche (apostrofi, caratteri speciali,
# nomi bilingue con parti aggiuntive).
# --block-prefix 20: usa i primi 20 caratteri di ciascuna colonna di join come chiave
#   di blocco, così ogni comune viene confrontato solo con i comuni della stessa regione.
# --latinize: normalizza caratteri accentati prima del confronto (à→a, è→e, ecc.)

echo "Eseguo fuzzy join (tometo_tomato)..."
tometo_tomato \
    "${TMPDIR_WORK}/eligendo.csv" \
    "${TMPDIR_WORK}/istat_norm.csv" \
    --join-pair "regione,DEN_REG" \
    --join-pair "comune,COMUNE_IT_NORM" \
    --latinize \
    --block-prefix 2 \
    --show-score \
    --add-field "PRO_COM_T" \
    --add-field "COMUNE_IT" \
    --add-field "COD_CATASTO" \
    --output-clean "${TMPDIR_WORK}/matched.csv" \
    --output-ambiguous "${TMPDIR_WORK}/ambiguous.csv" \
    --force \
    --quiet

MATCHED=$(wc -l < "${TMPDIR_WORK}/matched.csv")
AMBIGUOUS=$([ -f "${TMPDIR_WORK}/ambiguous.csv" ] && wc -l < "${TMPDIR_WORK}/ambiguous.csv" || echo 1)
echo "  Match puliti: $((MATCHED - 1))"
echo "  Ambigui: $((AMBIGUOUS - 1))"

# --- 5. Aggiunge cod_eligendo al risultato e salva ---
# tometo_tomato include nel CSV di output solo le colonne di join e quelle aggiunte
# con --add-field. Il cod_eligendo si recupera unendo il risultato con il CSV di input.

echo "Compongo output finale..."
duckdb -c "
COPY (
  WITH base AS (
    SELECT
      e.cod_eligendo,
      e.comune_originale AS nome_eligendo,
      m.COMUNE_IT AS nome_istat,
      m.regione,
      m.PRO_COM_T AS cod_istat,
      m.COD_CATASTO AS belfiore,
      ROUND(m.avg_score, 2) AS match_score
    FROM read_csv('${TMPDIR_WORK}/matched.csv', auto_detect=true) m
    JOIN read_csv('${TMPDIR_WORK}/eligendo.csv', auto_detect=true) e
      ON m.comune = e.comune AND m.regione = e.regione
  ),
  -- Per ogni cod_istat duplicato, tieni solo il match con score più alto
  best AS (
    SELECT cod_istat, MAX(match_score) AS best_score
    FROM base WHERE cod_istat IS NOT NULL
    GROUP BY cod_istat
  ),
  -- Override manuali per comuni fusi/rinominati non risolvibili automaticamente
  -- CASTEGNERO + NANTO → fusi in Castegnero Nanto (ISTAT 024129, Belfiore M439)
  overrides (cod_eligendo, nome_istat, cod_istat, belfiore) AS (
    VALUES
      ('050900270', 'Castegnero Nanto', '024129', 'M439'),
      ('050900710', 'Castegnero Nanto', '024129', 'M439')
  )
  SELECT
    b.cod_eligendo,
    b.nome_eligendo,
    COALESCE(o.nome_istat, CASE WHEN b.cod_istat IS NOT NULL AND b.match_score = best.best_score THEN b.nome_istat END) AS nome_istat,
    b.regione,
    COALESCE(o.cod_istat,  CASE WHEN b.cod_istat IS NOT NULL AND b.match_score = best.best_score THEN b.cod_istat END) AS cod_istat,
    COALESCE(o.belfiore,   CASE WHEN b.cod_istat IS NOT NULL AND b.match_score = best.best_score THEN b.belfiore END) AS belfiore,
    b.match_score
  FROM base b
  LEFT JOIN best ON b.cod_istat = best.cod_istat
  LEFT JOIN overrides o ON b.cod_eligendo = o.cod_eligendo
  ORDER BY b.cod_eligendo
) TO '${OUTPUT}' (HEADER, DELIMITER ',');
"

TOTAL=$(wc -l < "${OUTPUT}")
echo ""
echo "Fatto. ${OUTPUT}"
echo "Righe: $((TOTAL - 1)) comuni"
echo "Score minimo: $(duckdb -c "SELECT MIN(match_score) FROM read_csv('${OUTPUT}', auto_detect=true)" | grep -oE '[0-9]+\.[0-9]+')"

# --- Controlli qualità ---
echo ""
echo "Controlli qualità:"

NULL_COUNT=$(duckdb -csv -noheader -c "SELECT COUNT(*) FROM read_csv('${OUTPUT}', auto_detect=true) WHERE cod_istat IS NULL")
echo "  Senza cod_istat: ${NULL_COUNT}"

DUP_ISTAT=$(duckdb -csv -noheader -c "
SELECT cod_istat, COUNT(*) AS n
FROM read_csv('${OUTPUT}', auto_detect=true)
WHERE cod_istat IS NOT NULL
GROUP BY cod_istat HAVING n > 1
ORDER BY n DESC
LIMIT 5
" 2>/dev/null)
if [[ -n "$DUP_ISTAT" ]]; then
    echo "  ATTENZIONE: cod_istat duplicati (fusioni o falsi positivi):"
    echo "$DUP_ISTAT" | while IFS=',' read -r cod n; do
        names=$(duckdb -csv -noheader -c "SELECT nome_eligendo FROM read_csv('${OUTPUT}', auto_detect=true) WHERE cod_istat='${cod}'" 2>/dev/null | tr '\n' ' ')
        echo "    ${cod} (n=${n}): ${names}"
    done
else
    echo "  Nessun cod_istat duplicato"
fi
