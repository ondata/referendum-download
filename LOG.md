# LOG

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
