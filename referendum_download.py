#!/usr/bin/env python3
"""CLI per scaricare i dati dei referendum da eleapi.interno.gov.it in formato JSONLines."""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import requests

BASE_URL = "https://eleapi.interno.gov.it/siel/PX"
HEADERS = {
    "Origin": "https://elezioni.interno.gov.it",
    "Referer": "https://elezioni.interno.gov.it/",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def parse_url(url):
    """Estrae la data elezione dall'URL di elezioni.interno.gov.it."""
    # Supporta URL tipo: https://elezioni.interno.gov.it/risultati/20250608/referendum/...
    # Oppure direttamente la data: 20250608
    if re.match(r"^\d{8}$", url):
        return url
    match = re.search(r"/(\d{8})/", url)
    if match:
        return match.group(1)
    raise ValueError(f"Impossibile estrarre la data dall'URL: {url}")


def api_get(endpoint, session, retries=2, retry_delay=5):
    """Chiamata GET all'API con gestione errori e retry per errori di rete."""
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "Error" in data:
                raise RuntimeError(f"API error: {data['Error']}")
            return data
        except requests.exceptions.HTTPError:
            raise  # non retrare errori HTTP (404, ecc.)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < retries:
                time.sleep(retry_delay)
            else:
                raise


def get_enti(data_elez, session):
    """Scarica la lista di tutte le entità territoriali."""
    return api_get(f"getentiFI/DE/{data_elez}/TE/09", session)


def get_enti_estero(data_elez, session):
    """Scarica la lista delle entità estero."""
    return api_get(f"getentiFE/DE/{data_elez}/TE/09", session)


def get_scrutini_comune(data_elez, cod_reg, cod_prov, cod_com, session):
    """Scarica scrutini per un singolo comune."""
    endpoint = f"scrutiniFI/DE/{data_elez}/TE/09/RE/{cod_reg}/PR/{cod_prov}/CM/{cod_com}"
    return api_get(endpoint, session)


def get_scrutini_estero(data_elez, session):
    """Scarica scrutini estero a livello nazionale."""
    return api_get(f"scrutiniFE/DE/{data_elez}/TE/09", session)


def decode_cod_estero(cod):
    """Decodifica il codice nazione da getentiFE: cod='{ER}{NA:03d}' es. '2263' → (er=2, na=263)."""
    er = int(cod[0])
    na = int(cod[1:])
    return er, na


def get_scrutini_estero_nazione(data_elez, er, na, session):
    """Scarica scrutini per una singola nazione estero."""
    return api_get(f"scrutiniFE/DE/{data_elez}/TE/09/SK/01/ER/{er:02d}/NA/{na}", session)


def get_scrutini_regione(data_elez, cod_reg, session):
    """Scarica scrutini per una singola regione."""
    return api_get(f"scrutiniFI/DE/{data_elez}/TE/09/RE/{cod_reg}", session)


def get_scrutini_provincia(data_elez, cod_reg, cod_prov, session):
    """Scarica scrutini per una singola provincia."""
    return api_get(f"scrutiniFI/DE/{data_elez}/TE/09/RE/{cod_reg}/PR/{cod_prov}", session)


def get_votanti(data_elez, session):
    """Scarica affluenza nazionale + regionale."""
    return api_get(f"votantiFI/DE/{data_elez}/TE/09/SK/01", session)


def get_votanti_provincia(data_elez, cod_prov, session):
    """Scarica affluenza comunale per una provincia (cod_prov = 3 cifre Eligendo)."""
    return api_get(f"votantiFI/DE/{data_elez}/TE/09/SK/01/PR/{cod_prov}", session)


def get_votanti_estero(data_elez, session):
    """Scarica affluenza estero per ripartizione."""
    return api_get(f"votantiFE/DE/{data_elez}/TE/09", session)


def export_affluenza(data_elez, province, session, out_file, delay=0.5):
    """Salva affluenza.csv con righe per ogni livello (nazionale, regione, comune).

    province: lista di dict con 'cod' (9 cifre Eligendo) e 'desc' per ogni provincia.
    """
    import csv

    TIME_LABEL = {1: "12:00", 2: "19:00", 3: "23:00", 4: "finale"}
    FIELDS = [
        "livello", "cod_eligendo", "cod_istat", "cod_reg", "cod_prov", "cod_prov_istat",
        "denominazione", "elettori_m", "elettori_f", "elettori_t",
        "rilevazione", "ora", "dt_rilevazione",
        "sezioni_perv", "sezioni_tot", "votanti_m", "votanti_f", "votanti_t", "perc_vot",
    ]

    # Carica lookup comuni Eligendo → ISTAT
    lookup = {}
    lookup_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lookup", "lookup_eligendo_istat.csv")
    if os.path.exists(lookup_file):
        import csv as _csv
        with open(lookup_file) as lf:
            for row in _csv.DictReader(lf):
                lookup[row["cod_eligendo"]] = row["cod_istat"]

    # Carica lookup province Eligendo → ISTAT: chiave = (cod_reg, cod_prov_eligendo)
    lookup_prov = {}
    lookup_prov_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lookup", "lookup_province_eligendo_istat.csv")
    if os.path.exists(lookup_prov_file):
        import csv as _csv
        with open(lookup_prov_file) as lf:
            for row in _csv.DictReader(lf):
                lookup_prov[(row["cod_reg"], row["cod_prov_eligendo"])] = row["cod_prov_istat"]

    def make_rows(level, cod_eligendo, cod_reg, cod_prov, desc, ele_m, ele_f, ele_t, com_vot):
        rows = []
        if not com_vot:
            return rows
        cod_istat = lookup.get(cod_eligendo, "")
        cod_prov_istat = lookup_prov.get((cod_reg, cod_prov), "")
        for cv in com_vot:
            com_idx = cv.get("com")
            rows.append({
                "livello": level,
                "cod_eligendo": cod_eligendo,
                "cod_istat": cod_istat,
                "cod_reg": cod_reg,
                "cod_prov": cod_prov,
                "cod_prov_istat": cod_prov_istat,
                "denominazione": desc,
                "elettori_m": ele_m,
                "elettori_f": ele_f,
                "elettori_t": ele_t,
                "rilevazione": com_idx,
                "ora": TIME_LABEL.get(com_idx, str(com_idx)),
                "dt_rilevazione": str(cv.get("dt_com", "")),
                "sezioni_perv": cv.get("enti_p", 0),
                "sezioni_tot": cv.get("enti_t", 0),
                "votanti_m": cv.get("vot_m", ""),
                "votanti_f": cv.get("vot_f", ""),
                "votanti_t": cv.get("vot_t", 0),
                "perc_vot": cv.get("perc", ""),
            })
        return rows

    all_rows = []

    # 1. Nazionale + regionale
    try:
        d = get_votanti(data_elez, session)
        enti = d["enti"]
        ep = enti["ente_p"]
        all_rows += make_rows("nazionale", "", "", "", ep["desc"], ep.get("ele_m", ""), ep.get("ele_f", ""), ep["ele_t"], ep.get("com_vot"))
        for r in enti.get("enti_f", []):
            cod_reg = f"{r['cod']:02d}"
            all_rows += make_rows("regione", f"{r['cod']:02d}0000000", cod_reg, "", r["desc"], r.get("ele_m", ""), r.get("ele_f", ""), r["ele_t"], r.get("com_vot"))
    except RuntimeError as e:
        print(f"  AVVISO votanti nazionale: {e}", file=sys.stderr)

    # 2. Per ogni provincia → dati comunali
    print(f"  Scarico affluenza per {len(province)} province...")
    for i, prov in enumerate(province):
        cod_prov_full = prov["cod"]   # es. "010020000"
        cod_reg = cod_prov_full[0:2]  # es. "01"
        cod_prov = cod_prov_full[2:5] # es. "002"
        try:
            dp = get_votanti_provincia(data_elez, cod_prov, session)
            enti_p = dp["enti"]
            # Provincia
            prov_cod_eligendo = f"{cod_reg}{cod_prov}0000"
            ep = enti_p["ente_p"]
            all_rows += make_rows("provincia", prov_cod_eligendo, cod_reg, cod_prov, ep["desc"], ep.get("ele_m", ""), ep.get("ele_f", ""), ep["ele_t"], ep.get("com_vot"))
            # Comuni
            for com in enti_p.get("enti_f", []):
                cod_com = f"{int(com['cod']):04d}"
                cod_eligendo = f"{cod_reg}{cod_prov}{cod_com}"
                all_rows += make_rows("comune", cod_eligendo, cod_reg, cod_prov, com["desc"], com.get("ele_m", ""), com.get("ele_f", ""), com["ele_t"], com.get("com_vot"))
        except RuntimeError as e:
            print(f"  AVVISO {prov['desc']} ({cod_prov}): {e}", file=sys.stderr)

        if (i + 1) % 20 == 0:
            print(f"  [{i + 1}/{len(province)}] {prov['desc']}")
        if delay > 0 and i < len(province) - 1:
            time.sleep(delay)

    if not all_rows:
        return 0

    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)
    return len(all_rows)


def decode_cod(cod):
    """Decodifica il codice entità a 9 cifre in reg, prov, com."""
    # cod = "RRPPPCCCC"
    return cod[0:2], cod[2:5], cod[5:9]


def flatten_record(record):
    """Appiattisce un record scrutini: una riga per quesito."""
    rows = []
    api = record["data"]
    info = api["int"]

    base = {
        "cod": record["cod"],
        "area": record.get("area", ""),
        "livello": record.get("livello", ""),
    }

    if record.get("area") == "italia":
        base.update({
            "cod_reg": record.get("cod_reg", ""),
            "cod_prov": record.get("cod_prov", ""),
            "cod_com": record.get("cod_com", ""),
            "desc_com": info.get("desc_com", ""),
            "desc_prov": info.get("desc_prov", ""),
            "desc_reg": info.get("desc_reg", ""),
        })
    else:
        base.update({
            "cod_reg": "",
            "cod_prov": "",
            "cod_com": "",
            "desc_com": "",
            "desc_prov": "",
            "desc_reg": "",
        })

    base.update({
        "elettori_m": info.get("ele_m", ""),
        "elettori_f": info.get("ele_f", ""),
        "elettori_t": info.get("ele_t", ""),
        "sezioni_tot": info.get("sz_tot", ""),
    })

    for scheda in api.get("scheda", []):
        row = dict(base)
        row.update({
            "quesito_cod": scheda["cod"],
            "sezioni_perv": scheda.get("sz_perv", ""),
            "votanti_m": scheda.get("vot_m", ""),
            "votanti_f": scheda.get("vot_f", ""),
            "votanti_t": scheda.get("vot_t", ""),
            "perc_vot": scheda.get("perc_vot", ""),
            "sk_bianche": scheda.get("sk_bianche", ""),
            "sk_nulle": scheda.get("sk_nulle", ""),
            "sk_contestate": scheda.get("sk_contestate", ""),
            "voti_si": scheda.get("voti_si", ""),
            "voti_no": scheda.get("voti_no", ""),
            "perc_si": scheda.get("perc_si", ""),
            "perc_no": scheda.get("perc_no", ""),
        })
        rows.append(row)

    return rows


def jsonl_to_csv(jsonl_file, csv_file):
    """Converte un file JSONL in CSV, inferendo i campi dalla prima riga."""
    import csv
    with open(jsonl_file) as fin:
        first_line = fin.readline()
        if not first_line:
            return 0
        fields = list(json.loads(first_line).keys())
        fin.seek(0)
        rows = [json.loads(line) for line in fin]
    with open(csv_file, "w", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def export_flat(scrutini_file, flat_file):
    """Legge scrutini.jsonl e produce scrutini_flat.jsonl (una riga per comune per quesito)."""
    # Carica lookup comuni Eligendo → ISTAT
    lookup = {}
    lookup_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lookup", "lookup_eligendo_istat.csv")
    if os.path.exists(lookup_file):
        import csv
        with open(lookup_file) as lf:
            for row in csv.DictReader(lf):
                lookup[row["cod_eligendo"]] = row["cod_istat"]

    # Carica lookup province Eligendo → ISTAT: chiave = (cod_reg, cod_prov_eligendo)
    lookup_prov = {}
    lookup_prov_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lookup", "lookup_province_eligendo_istat.csv")
    if os.path.exists(lookup_prov_file):
        import csv
        with open(lookup_prov_file) as lf:
            for row in csv.DictReader(lf):
                lookup_prov[(row["cod_reg"], row["cod_prov_eligendo"])] = row["cod_prov_istat"]

    count = 0
    with open(scrutini_file) as fin, open(flat_file, "w") as fout:
        for line in fin:
            record = json.loads(line)
            for row in flatten_record(record):
                row["cod_istat"] = lookup.get(row.get("cod", ""), "")
                row["cod_prov_istat"] = lookup_prov.get((row.get("cod_reg", ""), row.get("cod_prov", "")), "")
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
    return count


def flatten_record_estero(record):
    """Appiattisce un record scrutini estero nazione: una riga per quesito."""
    rows = []
    api = record["data"]
    info = api["int"]

    base = {
        "cod": record["cod"],
        "livello": record.get("livello", ""),
        "cod_rip": info.get("cod_rip", ""),
        "desc_rip": info.get("desc_rip", ""),
        "cod_naz": info.get("cod_naz", ""),
        "desc_naz": info.get("desc_naz", ""),
        "elettori_t": info.get("ele_t", ""),
        "sezioni_tot": info.get("sz_tot", ""),
    }

    for scheda in api.get("scheda", []):
        row = dict(base)
        row.update({
            "quesito_cod": scheda["cod"],
            "sezioni_perv": scheda.get("sz_perv", ""),
            "votanti_t": scheda.get("vot_t", ""),
            "perc_vot": scheda.get("perc_vot", ""),
            "sk_bianche": scheda.get("sk_bianche", ""),
            "sk_nulle": scheda.get("sk_nulle", ""),
            "sk_contestate": scheda.get("sk_contestate", ""),
            "voti_si": scheda.get("voti_si", ""),
            "voti_no": scheda.get("voti_no", ""),
            "perc_si": scheda.get("perc_si", ""),
            "perc_no": scheda.get("perc_no", ""),
        })
        rows.append(row)

    return rows


def export_flat_estero(scrutini_file, flat_file):
    """Legge scrutini_estero.jsonl e produce scrutini_estero_flat.jsonl."""
    count = 0
    with open(scrutini_file) as fin, open(flat_file, "w") as fout:
        for line in fin:
            record = json.loads(line)
            for row in flatten_record_estero(record):
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
    return count


def export_scrutini_estero_nazioni(data_elez, nazioni, session, out_file, workers=4, delay=1.0):
    """Scarica scrutini per ogni nazione estero e salva in out_file (JSONL)."""

    def fetch_nazione(nazione):
        er, na = decode_cod_estero(nazione["cod"])
        result = nazione, get_scrutini_estero_nazione(data_elez, er, na, session)
        if delay > 0:
            time.sleep(delay)
        return result

    # Resume: leggi cod già scaricati
    existing_cods = set()
    if os.path.exists(out_file):
        with open(out_file) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("cod"):
                        existing_cods.add(rec["cod"])
                except json.JSONDecodeError:
                    pass

    nazioni_da_scaricare = [n for n in nazioni if n["cod"] not in existing_cods]
    if existing_cods:
        print(f"  Resume: {len(existing_cods)} nazioni già presenti, {len(nazioni_da_scaricare)} da scaricare")

    if not nazioni_da_scaricare:
        print(f"Scrutini estero già completi: {out_file} — skip")
        return len(existing_cods)

    results = {}
    errors = 0
    completed = 0
    print(f"  Scarico scrutini per {len(nazioni_da_scaricare)} nazioni con {workers} worker (delay {delay}s)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_idx = {executor.submit(fetch_nazione, n): i for i, n in enumerate(nazioni_da_scaricare)}
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            completed += 1
            try:
                nazione, data = future.result()
                results[idx] = (nazione, data)
            except Exception as e:
                nazione = nazioni_da_scaricare[idx]
                print(f"  ERRORE {nazione['desc']} ({nazione['cod']}): {e}", file=sys.stderr)
                errors += 1
            if completed % 20 == 0 or completed == len(nazioni_da_scaricare):
                print(f"  [{completed}/{len(nazioni_da_scaricare)}]")

    file_mode = "a" if existing_cods else "w"
    written = len(existing_cods)
    with open(out_file, file_mode) as f:
        for i in range(len(nazioni_da_scaricare)):
            if i in results:
                nazione, data = results[i]
                er, na = decode_cod_estero(nazione["cod"])
                record = {
                    "livello": "nazione",
                    "area": "estero",
                    "cod": nazione["cod"],
                    "cod_rip": er,
                    "cod_naz": na,
                    "desc": nazione["desc"],
                    "data": data,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

    if errors:
        print(f"  Errori: {errors}")
    return written


def export_affluenza_estero(data_elez, session, out_file):
    """Salva affluenza_estero.csv con righe per livello estero e ripartizione."""
    import csv

    FIELDS = [
        "livello", "cod_rip", "desc_rip",
        "elettori_t", "rilevazione", "dt_rilevazione",
        "sezioni_perv", "sezioni_tot", "votanti_t", "perc_vot",
    ]

    d = get_votanti_estero(data_elez, session)
    # votantiFE ha scheda[]; prendiamo SK/01 (indice 0)
    enti = d["scheda"][0]["enti"]

    rows = []
    ep = enti["ente_p"]
    for cv in ep.get("com_vot", []):
        rows.append({
            "livello": "estero",
            "cod_rip": "",
            "desc_rip": ep.get("desc", "ESTERO"),
            "elettori_t": ep.get("ele_t", ""),
            "rilevazione": cv.get("com", ""),
            "dt_rilevazione": str(cv.get("dt_com", "")),
            "sezioni_perv": cv.get("enti_p", ""),
            "sezioni_tot": cv.get("enti_t", ""),
            "votanti_t": cv.get("vot_t", ""),
            "perc_vot": cv.get("perc", ""),
        })

    for rip in enti.get("enti_f", []):
        for cv in rip.get("com_vot", []):
            rows.append({
                "livello": "ripartizione",
                "cod_rip": rip.get("cod", ""),
                "desc_rip": rip.get("desc", ""),
                "elettori_t": rip.get("ele_t", ""),
                "rilevazione": cv.get("com", ""),
                "dt_rilevazione": str(cv.get("dt_com", "")),
                "sezioni_perv": cv.get("enti_p", ""),
                "sezioni_tot": cv.get("enti_t", ""),
                "votanti_t": cv.get("vot_t", ""),
                "perc_vot": cv.get("perc", ""),
            })

    with open(out_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Scarica dati referendum da eleapi.interno.gov.it in formato JSONLines."
    )
    parser.add_argument(
        "url",
        help="URL della pagina referendum su elezioni.interno.gov.it oppure data in formato YYYYMMDD",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory di output (default: data)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Pausa in secondi tra le chiamate API (default: 1.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limita il numero di comuni da scaricare (0 = tutti, utile per test)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forza il re-download anche se i file esistono già",
    )
    parser.add_argument(
        "--solo-scrutini",
        action="store_true",
        help="Scarica solo gli scrutini (salta affluenza)",
    )
    parser.add_argument(
        "--solo-affluenza",
        action="store_true",
        help="Scarica solo l'affluenza (salta scrutini)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Numero di chiamate parallele per gli scrutini (default: 4)",
    )
    parser.add_argument(
        "--livello",
        choices=["rg", "pr", "cm"],
        default="cm",
        help="Livello geografico scrutini: rg=regioni, pr=province, cm=comuni (default: cm)",
    )
    args = parser.parse_args()

    data_elez = parse_url(args.url)
    out_dir = os.path.join(args.output_dir, data_elez)
    os.makedirs(out_dir, exist_ok=True)
    session = requests.Session()

    # 1. Entità Italia (skip se già presente, salvo --force)
    enti_file = os.path.join(out_dir, "enti.jsonl")
    if not args.force and os.path.exists(enti_file) and os.path.getsize(enti_file) > 0:
        print(f"Entità già presenti: {enti_file} — skip")
        enti_data = {"enti": []}
        with open(enti_file) as f:
            for line in f:
                enti_data["enti"].append(json.loads(line))
    else:
        print(f"Scarico entità per data {data_elez}...")
        enti_data = get_enti(data_elez, session)
        with open(enti_file, "w") as f:
            for e in enti_data["enti"]:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"  Entità salvate in {enti_file}")

    comuni = [e for e in enti_data["enti"] if e["tipo"] == "CM"]
    print(f"  {len(comuni)} comuni")

    if args.limit > 0:
        comuni = comuni[: args.limit]
        print(f"  Limitato a {len(comuni)} comuni (--limit)")

    # 2+3. Scrutini per livello geografico + estero (solo cm)
    if not args.solo_affluenza:
        out_file_map = {
            "cm": os.path.join(out_dir, "scrutini.jsonl"),
            "pr": os.path.join(out_dir, "scrutini_province.jsonl"),
            "rg": os.path.join(out_dir, "scrutini_regioni.jsonl"),
        }
        out_file = out_file_map[args.livello]

        written = 0
        errors = 0
        needs_flat_export = False

        if args.livello == "cm":
            # Resume: leggi cod già scaricati dal file esistente
            existing_cods = set()
            if not args.force and os.path.exists(out_file):
                with open(out_file) as f:
                    for line in f:
                        try:
                            rec = json.loads(line)
                            if rec.get("cod"):
                                existing_cods.add(rec["cod"])
                        except json.JSONDecodeError:
                            pass
                written = len(existing_cods)

            comuni_da_scaricare = [c for c in comuni if c["cod"] not in existing_cods]

            if existing_cods:
                print(f"  Resume: {len(existing_cods)} comuni già presenti, {len(comuni_da_scaricare)} da scaricare")

            if not comuni_da_scaricare and "estero" in existing_cods:
                print(f"Scrutini già completi: {out_file} — skip (usa --force per riscaricare)")
            else:
                needs_flat_export = True

                def fetch_comune(comune):
                    cod = comune["cod"]
                    cod_reg, cod_prov, cod_com = decode_cod(cod)
                    result = comune, get_scrutini_comune(data_elez, cod_reg, cod_prov, cod_com, session)
                    if args.delay > 0:
                        time.sleep(args.delay)
                    return result

                results = {}
                completed = 0
                if comuni_da_scaricare:
                    print(f"  Scarico scrutini comuni con {args.workers} worker paralleli (delay {args.delay}s)...")
                    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                        future_to_idx = {executor.submit(fetch_comune, c): i for i, c in enumerate(comuni_da_scaricare)}
                        for future in concurrent.futures.as_completed(future_to_idx):
                            idx = future_to_idx[future]
                            completed += 1
                            try:
                                comune, data = future.result()
                                results[idx] = (comune, data)
                            except Exception as e:
                                comune = comuni_da_scaricare[idx]
                                print(f"  ERRORE {comune['desc']} ({comune['cod']}): {e}", file=sys.stderr)
                                errors += 1
                            if completed % 50 == 0 or completed == len(comuni_da_scaricare):
                                print(f"  [{completed}/{len(comuni_da_scaricare)}]")

                file_mode = "a" if existing_cods else "w"
                with open(out_file, file_mode) as f:
                    for i in range(len(comuni_da_scaricare)):
                        if i in results:
                            comune, data = results[i]
                            cod = comune["cod"]
                            cod_reg, cod_prov, cod_com = decode_cod(cod)
                            record = {
                                "livello": "comune",
                                "area": "italia",
                                "cod": cod,
                                "cod_reg": cod_reg,
                                "cod_prov": cod_prov,
                                "cod_com": cod_com,
                                "data": data,
                            }
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")
                            written += 1

                    # Estero (solo se non già presente)
                    if "estero" not in existing_cods:
                        print("Scarico scrutini estero...")
                        try:
                            data_estero = get_scrutini_estero(data_elez, session)
                            record = {"livello": "nazionale", "area": "estero", "cod": "estero", "data": data_estero}
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")
                            written += 1
                            print("  Estero OK")
                        except Exception as e:
                            print(f"  ERRORE estero: {e}", file=sys.stderr)
                            errors += 1

        elif args.livello == "pr":
            if not args.force and os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                print(f"Scrutini già presenti: {out_file} — skip (usa --force per riscaricare)")
            else:
                needs_flat_export = True
                province_enti = [e for e in enti_data["enti"] if e["tipo"] == "PR"]
                print(f"  Scarico scrutini per {len(province_enti)} province...")
                with open(out_file, "w") as f:
                    for i, ente in enumerate(province_enti):
                        cod = ente["cod"]
                        cod_reg = cod[0:2]
                        cod_prov = cod[2:5]
                        try:
                            data = get_scrutini_provincia(data_elez, cod_reg, cod_prov, session)
                            record = {
                                "livello": "provincia",
                                "area": "italia",
                                "cod": cod,
                                "cod_reg": cod_reg,
                                "cod_prov": cod_prov,
                                "cod_com": "",
                                "data": data,
                            }
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")
                            written += 1
                        except Exception as e:
                            print(f"  ERRORE {ente['desc']} ({cod}): {e}", file=sys.stderr)
                            errors += 1
                        if args.delay > 0 and i < len(province_enti) - 1:
                            time.sleep(args.delay)

        elif args.livello == "rg":
            if not args.force and os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                print(f"Scrutini già presenti: {out_file} — skip (usa --force per riscaricare)")
            else:
                needs_flat_export = True
                regioni_enti = [e for e in enti_data["enti"] if e["tipo"] == "RE"]
                print(f"  Scarico scrutini per {len(regioni_enti)} regioni...")
                with open(out_file, "w") as f:
                    for i, ente in enumerate(regioni_enti):
                        cod = ente["cod"]
                        cod_reg = cod[0:2]
                        try:
                            data = get_scrutini_regione(data_elez, cod_reg, session)
                            record = {
                                "livello": "regione",
                                "area": "italia",
                                "cod": cod,
                                "cod_reg": cod_reg,
                                "cod_prov": "",
                                "cod_com": "",
                                "data": data,
                            }
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")
                            written += 1
                        except Exception as e:
                            print(f"  ERRORE {ente['desc']} ({cod}): {e}", file=sys.stderr)
                            errors += 1
                        if args.delay > 0 and i < len(regioni_enti) - 1:
                            time.sleep(args.delay)

        if needs_flat_export:
            print(f"\nCompletato: {written} record scritti in {out_file}")
            if errors:
                print(f"Errori: {errors}")

            # Export flat
            flat_stem = os.path.splitext(out_file)[0]
            flat_file = flat_stem + "_flat.jsonl"
            flat_csv = flat_stem + "_flat.csv"
            print("Genero export flat...")
            flat_count = export_flat(out_file, flat_file)
            print(f"  {flat_count} righe scritte in {flat_file}")
            jsonl_to_csv(flat_file, flat_csv)
            print(f"  {flat_count} righe scritte in {flat_csv}")

    # 4. Affluenza comunale (votantiFI per provincia)
    if not args.solo_scrutini:
        province = [e for e in enti_data["enti"] if e["tipo"] == "PR"]
        affluenza_file = os.path.join(out_dir, "affluenza.csv")
        if not args.force and os.path.exists(affluenza_file) and os.path.getsize(affluenza_file) > 0:
            print(f"Affluenza già presente: {affluenza_file} — skip (usa --force per riscaricare)")
        else:
            print("\nScarico affluenza per comune...")
            aff_count = export_affluenza(data_elez, province, session, affluenza_file, delay=args.delay)
            print(f"  {aff_count} righe scritte in {affluenza_file}")

    # 5. Entità estero
    enti_estero_file = os.path.join(out_dir, "enti_estero.jsonl")
    if not args.force and os.path.exists(enti_estero_file) and os.path.getsize(enti_estero_file) > 0:
        print(f"Entità estero già presenti: {enti_estero_file} — skip")
        enti_estero = []
        with open(enti_estero_file) as f:
            for line in f:
                enti_estero.append(json.loads(line))
    else:
        print(f"Scarico entità estero...")
        enti_estero_data = get_enti_estero(data_elez, session)
        enti_estero = enti_estero_data["enti"]
        with open(enti_estero_file, "w") as f:
            for e in enti_estero:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"  {len(enti_estero)} entità estero salvate in {enti_estero_file}")

    nazioni = [e for e in enti_estero if e["tipo"] == "NA"]
    print(f"  {len(nazioni)} nazioni estero")

    # 6. Scrutini per nazione estero
    if not args.solo_affluenza:
        scrutini_estero_file = os.path.join(out_dir, "scrutini_estero.jsonl")
        written_estero = export_scrutini_estero_nazioni(
            data_elez, nazioni, session, scrutini_estero_file,
            workers=args.workers, delay=0,
        )
        if written_estero:
            print(f"\nCompletato: {written_estero} nazioni scritte in {scrutini_estero_file}")
            flat_estero_jsonl = os.path.join(out_dir, "scrutini_estero_flat.jsonl")
            flat_estero_csv = os.path.join(out_dir, "scrutini_estero_flat.csv")
            print("Genero export flat estero...")
            flat_count = export_flat_estero(scrutini_estero_file, flat_estero_jsonl)
            print(f"  {flat_count} righe scritte in {flat_estero_jsonl}")
            jsonl_to_csv(flat_estero_jsonl, flat_estero_csv)
            print(f"  {flat_count} righe scritte in {flat_estero_csv}")

    # 7. Affluenza estero
    if not args.solo_scrutini:
        affluenza_estero_file = os.path.join(out_dir, "affluenza_estero.csv")
        if not args.force and os.path.exists(affluenza_estero_file) and os.path.getsize(affluenza_estero_file) > 0:
            print(f"Affluenza estero già presente: {affluenza_estero_file} — skip (usa --force per riscaricare)")
        else:
            print("\nScarico affluenza estero...")
            try:
                aff_estero_count = export_affluenza_estero(data_elez, session, affluenza_estero_file)
                print(f"  {aff_estero_count} righe scritte in {affluenza_estero_file}")
            except Exception as e:
                print(f"  ERRORE affluenza estero: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
