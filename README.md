# Hunting Bazar Scraper

Jednoduchý Python skript pro automatické sledování nových inzerátů na **Hunting bazaru** (bazar.hunting-shop.cz).  
Skript projde inzeráty za posledních X dní, uloží je do přehledného HTML souboru a volitelně je může odeslat e-mailem jako přílohu.

Projekt je určený pro osobní použití a automatizaci přehledu nových nabídek.

---

## Funkce

- Scraping inzerátů z Hunting bazaru
- Filtrování pouze na nové inzeráty za poslední N dní
- Generování přehledného HTML reportu:
  - řazení podle data a ceny
  - filtrování podle místa prodeje
- Volitelné odeslání výsledku e-mailem (SMTP, TLS)
- Ochrana proti 403 pomocí realistických HTTP hlaviček
- Stránkování a šetrné timeouty

---

## Struktura projektu

```
.
├── main.py            # Hlavní skript
├── requirements.txt   # Python závislosti
├── install.sh         # Instalace projektu a virtualenvu
├── run.sh             # Spuštění skriptu
└── vysledek_inzeraty.html  # Výstup (generuje se po spuštění)
```

---

## Požadavky

- Linux
- Python 3.13.5+
- git
- bash

---

## Instalace

Nejjednodušší způsob je použít instalační skript:

```bash
bash install.sh
```

Skript:
- naklonuje nebo aktualizuje repozitář do složky Dokumenty
- vytvoří virtuální prostředí
- nainstaluje potřebné závislosti

---

## Spuštění

```bash
bash run.sh
```

Po spuštění:
- proběhne stažení inzerátů
- vytvoří se soubor `vysledek_inzeraty.html`
- soubor lze otevřít v libovolném prohlížeči

---

## Konfigurace

V souboru `main.py` lze upravit:

```python
DAYS_BACK = 2            # Kolik dní zpětně sledovat
SEND_EMAIL = False       # True = posílat e-mail, False = jen HTML
```

### E-mail (volitelné)

```python
SMTP_SERVER = "smtp.protonmail.ch"
SMTP_PORT = 587
SMTP_USER = "odesilatel@domena.cz"
SMTP_PASSWORD = "heslo"
EMAIL_TO = "prijemce@domena.cz"
```

Pokud je `SEND_EMAIL = True`,:
- HTML obsah se odešle v těle e-mailu
- zároveň se přiloží jako soubor

---

## Výstup

Výsledný HTML soubor obsahuje:
- datum inzerátu
- název s odkazem
- místo prodeje
- cenu
- celkový počet nalezených inzerátů

Soubor je plně interaktivní (řazení, filtrování) bez potřeby serveru.

---

## Poznámky

- Skript používá zpoždění mezi požadavky, aby byl šetrný k serveru
- Struktura webu se může změnit – v takovém případě je potřeba upravit selektory
- Projekt je určený pro studijní a osobní účely

---

## Licence

MIT License  
Používej rozumně a férově.
