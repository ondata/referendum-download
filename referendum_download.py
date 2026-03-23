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


def api_get(endpoint, session):
    """Chiamata GET all'API con gestione errori."""
    url = f"{BASE_URL}/{endpoint}"
    resp = session.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "Error" in data:
        raise RuntimeError(f"API error: {data['Error']}")
    return data


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


def get_votanti(data_elez, session):
    """Scarica affluenza nazionale + regionale."""
    return api_get(f"votantiFI/DE/{data_elez}/TE/09/SK/01", session)


def get_votanti_provincia(data_elez, cod_prov, session):
    """Scarica affluenza comunale per una provincia (cod_prov = 3 cifre Eligendo)."""
    return api_get(f"votantiFI/DE/{data_elez}/TE/09/SK/01/PR/{cod_prov}", session)


def export_affluenza(data_elez, province, session, out_file, delay=0.5):
    """Salva affluenza.csv con righe per ogni livello (nazionale, regione, comune).

    province: lista di dict con 'cod' (9 cifre Eligendo) e 'desc' per ogni provincia.
    """
    import csv

    TIME_LABEL = {1: "12:00", 2: "19:00", 3: "23:00", 4: "finale"}
    FIELDS = [
        "livello", "cod_eligendo", "cod_istat", "cod_reg", "cod_prov", "cod_prov_istat",
        "denominazione", "elettori_t",
        "rilevazione", "ora", "dt_rilevazione",
        "sezioni_perv", "sezioni_tot", "votanti_t", "perc_vot",
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

    def make_rows(level, cod_eligendo, cod_reg, cod_prov, desc, ele_t, com_vot):
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
                "elettori_t": ele_t,
                "rilevazione": com_idx,
                "ora": TIME_LABEL.get(com_idx, str(com_idx)),
                "dt_rilevazione": str(cv.get("dt_com", "")),
                "sezioni_perv": cv.get("enti_p", 0),
                "sezioni_tot": cv.get("enti_t", 0),
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
        all_rows += make_rows("nazionale", "", "", "", ep["desc"], ep["ele_t"], ep.get("com_vot"))
        for r in enti.get("enti_f", []):
            cod_reg = f"{r['cod']:02d}"
            all_rows += make_rows("regione", f"{r['cod']:02d}0000000", cod_reg, "", r["desc"], r["ele_t"], r.get("com_vot"))
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
            all_rows += make_rows("provincia", prov_cod_eligendo, cod_reg, cod_prov, ep["desc"], ep["ele_t"], ep.get("com_vot"))
            # Comuni
            for com in enti_p.get("enti_f", []):
                cod_com = f"{int(com['cod']):04d}"
                cod_eligendo = f"{cod_reg}{cod_prov}{cod_com}"
                all_rows += make_rows("comune", cod_eligendo, cod_reg, cod_prov, com["desc"], com["ele_t"], com.get("com_vot"))
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

    # 2+3. Scrutini per comune + estero
    if not args.solo_affluenza:
        out_file = os.path.join(out_dir, "scrutini.jsonl")
        if not args.force and os.path.exists(out_file) and os.path.getsize(out_file) > 0:
            print(f"Scrutini già presenti: {out_file} — skip (usa --force per riscaricare)")
        else:
            written = 0
            errors = 0

            def fetch_comune(comune):
                cod = comune["cod"]
                cod_reg, cod_prov, cod_com = decode_cod(cod)
                result = comune, get_scrutini_comune(data_elez, cod_reg, cod_prov, cod_com, session)
                if args.delay > 0:
                    time.sleep(args.delay)
                return result

            results = {}
            completed = 0
            print(f"  Scarico scrutini con {args.workers} worker paralleli (delay {args.delay}s)...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                future_to_idx = {executor.submit(fetch_comune, c): i for i, c in enumerate(comuni)}
                for future in concurrent.futures.as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    completed += 1
                    try:
                        comune, data = future.result()
                        results[idx] = (comune, data)
                    except Exception as e:
                        comune = comuni[idx]
                        print(f"  ERRORE {comune['desc']} ({comune['cod']}): {e}", file=sys.stderr)
                        errors += 1
                    if completed % 50 == 0 or completed == len(comuni):
                        print(f"  [{completed}/{len(comuni)}]")

            with open(out_file, "w") as f:
                for i in range(len(comuni)):
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

                # Estero
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

            print(f"\nCompletato: {written} record scritti in {out_file}")
            if errors:
                print(f"Errori: {errors}")

            # Export flat
            flat_file = os.path.join(out_dir, "scrutini_flat.jsonl")
            print("Genero export flat...")
            flat_count = export_flat(out_file, flat_file)
            print(f"  {flat_count} righe scritte in {flat_file}")

            # Export flat CSV
            flat_csv = os.path.join(out_dir, "scrutini_flat.csv")
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


if __name__ == "__main__":
    main()
