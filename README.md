# Hunting Bazar Monitor

Automatizovaný Python scraper, který pravidelně sleduje nové inzeráty z webu **bazar.hunting-shop.cz** (sekce zbraně), filtruje je podle stáří a generuje přehledný HTML dashboard.

Výstup lze:
- zobrazit jako lokální HTML soubor
- automaticky nahrát na FTP
- volitelně odeslat e-mailem jako přílohu

Projekt je navržený tak, aby šel snadno spouštět na Windows i Linuxu a aktualizovat jedním příkazem.

---

## Funkce

- Scraping inzerátů z více stránek bazaru
- Filtrování podle:
  - stáří inzerátu (X dní zpětně)
  - názvu
  - lokality
  - ceny
  - data a času
- Interaktivní HTML dashboard:
  - fulltextové vyhledávání
  - řazení podle ceny a data
  - responzivní zobrazení pro mobil
- Automatický upload výsledku na FTP
- Volitelné odeslání e-mailem
- Podpora virtuálního prostředí (venv)

---

## Ukázka výstupu

Výsledkem běhu skriptu je soubor:

```
inzeraty.html
```

Ten obsahuje:
- počet nalezených inzerátů
- přehlednou tabulku
- klientské filtrování a řazení (JavaScript)

---

## Struktura projektu

```
.
├── main.py
├── requirements.txt
├── data_sample.py
├── run.bat
├── run.sh
├── update.bat
├── update.sh
├── install.sh
└── README.md
```

---

## Instalace (Linux)

Nejjednodušší cesta je použít instalační skript:

```bash
curl -fsSL https://hb.krystofklika.cz/install.sh | bash
```

Skript:
- naklonuje nebo aktualizuje repozitář
- vytvoří virtuální prostředí
- nainstaluje závislosti
- připraví `data.py` z `data_sample.py`

---

## Instalace (ručně)

### 1. Klonování repozitáře

```bash
git clone https://github.com/joudar11/hunting
cd hunting
```

### 2. Virtuální prostředí

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Závislosti

```bash
pip install -r requirements.txt
```

### 4. Konfigurace

Zkopíruj a uprav konfigurační soubor:

```bash
cp data_sample.py data.py
```

Vyplň:
- SMTP údaje (pokud chceš posílat e-maily)
- FTP přístup (pokud chceš uploadovat HTML)

---

## Spuštění

### Windows

```bat
run.bat
```

### Linux

```bash
bash run.sh
```

Po spuštění:
- se stáhnou nové inzeráty
- vygeneruje se `inzeraty.html`
- soubor se případně odešle e-mailem nebo nahraje na FTP

---

## Aktualizace projektu

### Windows

```bat
update.bat
```

### Linux

```bash
bash update.sh
```

---

## Konfigurace v `main.py`

```python
DAYS_BACK = 7          # Kolik dní zpětně sledovat
SEND_EMAIL = False    # Odeslat výsledek e-mailem
UPLOAD_TO_FTP = True  # Nahrát výsledek na FTP
```

---

## Autor

Kryštof Klika

README.md je soubor vygenerovaný AI.