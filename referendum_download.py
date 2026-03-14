#!/usr/bin/env python3
"""CLI per scaricare i dati dei referendum da eleapi.interno.gov.it in formato JSONLines."""

import argparse
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


def export_flat(scrutini_file, flat_file):
    """Legge scrutini.jsonl e produce scrutini_flat.jsonl (una riga per comune per quesito)."""
    count = 0
    with open(scrutini_file) as fin, open(flat_file, "w") as fout:
        for line in fin:
            record = json.loads(line)
            for row in flatten_record(record):
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
    args = parser.parse_args()

    data_elez = parse_url(args.url)
    out_dir = os.path.join(args.output_dir, data_elez)
    out_file = os.path.join(out_dir, "scrutini.jsonl")

    # Idempotenza: se il file esiste e contiene dati, non riscarica
    if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
        print(f"File già esistente: {out_file} — skip (cancellalo per riscaricare)")
        sys.exit(0)

    os.makedirs(out_dir, exist_ok=True)
    session = requests.Session()

    # 1. Scarica entità Italia
    print(f"Scarico entità per data {data_elez}...")
    enti_data = get_enti(data_elez, session)
    comuni = [e for e in enti_data["enti"] if e["tipo"] == "CM"]
    print(f"  Trovati {len(comuni)} comuni")

    if args.limit > 0:
        comuni = comuni[: args.limit]
        print(f"  Limitato a {len(comuni)} comuni (--limit)")

    # Salva enti come file di riferimento
    enti_file = os.path.join(out_dir, "enti.jsonl")
    with open(enti_file, "w") as f:
        for e in enti_data["enti"]:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"  Entità salvate in {enti_file}")

    # 2. Scarica scrutini per ogni comune
    written = 0
    errors = 0
    with open(out_file, "w") as f:
        for i, comune in enumerate(comuni):
            cod = comune["cod"]
            cod_reg, cod_prov, cod_com = decode_cod(cod)
            desc = comune["desc"]

            try:
                data = get_scrutini_comune(data_elez, cod_reg, cod_prov, cod_com, session)
                # Aggiungi metadati
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
            except Exception as e:
                print(f"  ERRORE {desc} ({cod}): {e}", file=sys.stderr)
                errors += 1

            # Progresso
            if (i + 1) % 50 == 0 or (i + 1) == len(comuni):
                print(f"  [{i + 1}/{len(comuni)}] {desc}")

            if args.delay > 0 and i < len(comuni) - 1:
                time.sleep(args.delay)

        # 3. Scarica scrutini estero
        print("Scarico scrutini estero...")
        try:
            data_estero = get_scrutini_estero(data_elez, session)
            record = {
                "livello": "nazionale",
                "area": "estero",
                "cod": "estero",
                "data": data_estero,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            print("  Estero OK")
        except Exception as e:
            print(f"  ERRORE estero: {e}", file=sys.stderr)
            errors += 1

    print(f"\nCompletato: {written} record scritti in {out_file}")
    if errors:
        print(f"Errori: {errors}")

    # 4. Export flat (una riga per comune per quesito)
    flat_file = os.path.join(out_dir, "scrutini_flat.jsonl")
    print(f"Genero export flat...")
    flat_count = export_flat(out_file, flat_file)
    print(f"  {flat_count} righe scritte in {flat_file}")


if __name__ == "__main__":
    main()
