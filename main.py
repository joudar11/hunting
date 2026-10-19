import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from collections import Counter
import html
import re
import statistics
import subprocess
import time
import smtplib
import os
import unicodedata
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from data import SMTP_PASSWORD, SMTP_PORT, SMTP_SERVER, SMTP_USER, FTP_HOST, FTP_PASS, FTP_PATH, FTP_USER, EMAIL_TO

# KONFIGURACE
DAYS_BACK = 7
BASE_URL = "https://bazar.hunting-shop.cz/sekce/51-bazar-zbrane/"
OUTPUT_FILE = "inzeraty.html"

SEND_EMAIL = False  # True, pokud chceš výsledek posílat emailem.
UPLOAD_TO_FTP = True

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    "Referer": "https://bazar.hunting-shop.cz/"
}


def upload_to_ftp(html_content):
    try:
        url = f"ftp://{FTP_HOST}/{FTP_PATH}"
        subprocess.run(
            ['curl', '--ssl-reqd', '-u', f"{FTP_USER}:{FTP_PASS}", '-T', '-', url],
            input=html_content.encode('utf-8'),
            capture_output=True,
            check=True
        )
        print(f"Soubor byl úspěšně nahrán přes curl na: {FTP_HOST}")
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)
        print(f"Chyba při nahrávání přes curl: {error_message}")


def send_email(html_content):
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Hunting Bazar: Nové inzeráty za poslední {DAYS_BACK} dny"

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {OUTPUT_FILE}")
        msg.attach(part)
        msg.attach(MIMEText("V příloze nalezneš výpis inzerátů.", 'html'))
    else:
        msg.attach(MIMEText(html_content, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("E-mail byl úspěšně odeslán")
    except Exception as e:
        print(f"Chyba při odesílání e-mailu: {e}")


def scrape_hunting_bazar():
    current_date = datetime.now()
    threshold_date = (current_date - timedelta(days=DAYS_BACK)).replace(hour=0, minute=0, second=0, microsecond=0)

    all_ads = []
    page = 1
    continue_scraping = True

    print(f"Hledám inzeráty od: {threshold_date.strftime('%d. %m. %Y')}")

    session = requests.Session()
    session.headers.update(HEADERS)

    while continue_scraping:
        params = {'filtr': 'n', 'list': page, 'search': ''}

        try:
            response = session.get(BASE_URL, params=params, timeout=30)

            if response.status_code == 403:
                print("Chyba 403: Přístup odepřen. Server tě blokuje.")
                break

            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            ad_blocks = soup.find_all('div', class_='zbozi_okno')

            if not ad_blocks:
                print("Žádné další inzeráty nenalezeny.")
                break

            for block in ad_blocks:
                date_span = block.find('span', style=re.compile(r'font-size: 10px'))
                if not date_span:
                    continue

                date_match = re.search(r'(\d{2}\. \d{2}\. \d{4}), (\d{2}:\d{2}:\d{2})', date_span.text)
                if not date_match:
                    continue

                ad_date_str = date_match.group(1)
                ad_time_str = date_match.group(2)
                ad_date_dt = datetime.strptime(ad_date_str, '%d. %m. %Y')

                if ad_date_dt < threshold_date:
                    continue_scraping = False
                    break

                title_tag = block.find('h2', class_='zbozi_nazev').find('a')
                title = title_tag.text.strip()
                link = title_tag['href']
                if not link.startswith('http'):
                    link = "https://bazar.hunting-shop.cz/" + link

                price_tag = block.find('strong', string=re.compile(r'Cena:'))
                price = price_tag.text.replace('Cena:', '').strip() if price_tag else "neuvedena"

                location_tag = block.find('span', class_='kontakt')
                location = location_tag.text.split('|')[0].strip() if location_tag else "Neznámo"

                all_ads.append({
                    'title': title,
                    'price': price,
                    'location': location,
                    'date': ad_date_str,
                    'time': ad_time_str,
                    'link': link
                })

            print(f"Stránka {page} hotova...")
            page += 1
            time.sleep(0.33)

        except Exception as e:
            print(f"Chyba: {e}")
            break

    generate_html(all_ads)


# ---------------------------------------------------------------------------
# HTML výstup
# ---------------------------------------------------------------------------

def esc(value):
    """Escapuje text pro vložení do HTML (obsah i atributy)."""
    return html.escape(str(value), quote=True)


def parse_price(price_text):
    """'25 000,- Kč' -> 25000; 'Dohodou' / 'neuvedena' -> None."""
    match = re.search(r'\d[\d\s\u00a0.]*', price_text or "")
    if not match:
        return None
    digits = re.sub(r'\D', '', match.group(0))
    return int(digits) if digits else None


def format_czk(number):
    return f"{number:,}".replace(",", "\u00a0") + "\u00a0Kč"


def format_price(price_text, price_num):
    clean = " ".join((price_text or "").split())
    if price_num is not None:
        has_letters = re.search(r'[^\W\d_]', clean)
        if re.search(r'k[čc]', clean, re.IGNORECASE) or not has_letters:
            return format_czk(price_num)
        return clean
    if not clean or clean.lower() == "neuvedena":
        return "Cena neuvedena"
    return clean


def safe_link(link):
    return link if link.lower().startswith(("http://", "https://")) else "#"


def sort_key_cs(text):
    """Řazení bez ohledu na diakritiku (Ústí nepadne až za Zlín)."""
    return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode().lower()


PIN_ICON = ('<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/>'
            '<circle cx="12" cy="9.5" r="2.5"/></svg>')

SEARCH_ICON = ('<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" '
               'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>')

FILTER_ICON = ('<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" '
               'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="M4 6h16M7 12h10M10 18h4"/></svg>')


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="cs" class="no-js">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Hunting Bazar – inzeráty %%START%% až %%END%%</title>
<script>document.documentElement.classList.remove('no-js');</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #e8eae3;
  --surface: #f7f8f4;
  --surface-hover: #eef0e8;
  --line: #d3d7cb;
  --ink: #1b221c;
  --muted: #5d695e;
  --faint: #8a948a;
  --loden: #2f3d30;
  --on-loden: #eef1e9;
  --on-loden-muted: #b4c0b2;
  --moss: #55704a;
  --blaze: #d9520a;
  --blaze-soft: rgba(217, 82, 10, .13);
  --focus: #55704a;
  --radius: 10px;
  --font: "Barlow", system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif;
  --font-cond: "Barlow Condensed", "Arial Narrow", "Roboto Condensed", system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #121813;
    --surface: #19211a;
    --surface-hover: #1f2920;
    --line: #2b362c;
    --ink: #e3e8df;
    --muted: #93a094;
    --faint: #66726a;
    --loden: #1f2b21;
    --on-loden: #e3e8df;
    --on-loden-muted: #93a094;
    --moss: #8fb07f;
    --blaze: #ff7a2e;
    --blaze-soft: rgba(255, 122, 46, .16);
    --focus: #8fb07f;
  }
}

* { box-sizing: border-box; }
[hidden] { display: none !important; }
html, body { margin: 0; }
body {
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.5;
  background: var(--bg);
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; }
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.no-js .js-only, .no-js .when .abs { display: none !important; }

/* ---------- Hlavička ---------- */
.masthead {
  background: var(--loden);
  color: var(--on-loden);
  border-bottom: 4px solid var(--blaze);
}
.masthead-inner {
  max-width: 1240px;
  margin: 0 auto;
  padding: 44px 24px 36px;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px 48px;
}
h1 {
  font-family: var(--font-cond);
  font-weight: 700;
  font-size: clamp(2.8rem, 7vw, 4.75rem);
  line-height: .9;
  letter-spacing: -.01em;
  margin: 0 0 14px;
}
.lede { margin: 0; color: var(--on-loden-muted); max-width: 46ch; }
.tally { display: flex; gap: 32px; flex-wrap: wrap; margin: 0; }
.tally div { display: flex; flex-direction: column; }
.tally dt { order: 2; font-size: .9rem; color: var(--on-loden-muted); }
.tally dd {
  order: 1;
  margin: 0;
  font-family: var(--font-cond);
  font-weight: 600;
  font-size: 2.25rem;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.tally .is-blaze dd { color: var(--blaze); }

/* ---------- Rozložení ---------- */
.layout {
  max-width: 1240px;
  margin: 0 auto;
  padding: 28px 24px 64px;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 32px;
  align-items: start;
}

/* ---------- Filtry ---------- */
.filters { position: sticky; top: 20px; }
.filters-toggle { display: none; }
.filter-group { padding: 0 0 20px; margin: 0 0 20px; border-bottom: 1px solid var(--line); }
.filter-group:last-of-type { border-bottom: 0; }
.filter-label { display: block; font-weight: 600; font-size: .95rem; margin-bottom: 8px; }

input[type="search"], input[type="number"], input[type="datetime-local"], select {
  width: 100%;
  font: inherit;
  font-size: .95rem;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 9px 12px;
  transition: border-color .15s;
}
input:hover, select:hover { border-color: var(--faint); }
input:focus-visible, select:focus-visible { outline: none; border-color: var(--focus); box-shadow: 0 0 0 3px color-mix(in srgb, var(--focus) 25%, transparent); }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.stack { display: grid; gap: 8px; margin-top: 10px; }

.check { display: flex; align-items: center; gap: 10px; margin-top: 12px; cursor: pointer; font-size: .95rem; }
.check input { width: 17px; height: 17px; accent-color: var(--moss); margin: 0; }

.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip, .seg button, .btn-text {
  font: inherit;
  font-size: .9rem;
  font-weight: 500;
  color: var(--ink);
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 13px;
  cursor: pointer;
  transition: background-color .15s, border-color .15s, color .15s;
}
.chip:hover, .seg button:hover { border-color: var(--faint); }
.chip[aria-pressed="true"], .seg button[aria-pressed="true"] {
  background: var(--ink);
  border-color: var(--ink);
  color: var(--bg);
}
details summary { cursor: pointer; font-size: .9rem; color: var(--muted); margin-top: 12px; }
.btn-text { border: 0; padding: 4px 0; color: var(--moss); font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }

/* ---------- Lišta s hledáním ---------- */
.toolbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
  padding: 10px 0 12px;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.search { position: relative; flex: 1 1 280px; }
.search svg { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--faint); pointer-events: none; }
.search input { padding-left: 40px; padding-right: 40px; font-size: 1rem; }
.search kbd {
  position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
  font-family: inherit; font-size: .8rem; color: var(--faint);
  border: 1px solid var(--line); border-radius: 5px; padding: 0 6px; pointer-events: none;
}
.seg { display: flex; flex-wrap: wrap; gap: 6px; }
.status { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin: 4px 0 12px; font-size: .9rem; color: var(--muted); }

/* ---------- Výpis inzerátů ---------- */
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.ad {
  position: relative;
  display: grid;
  grid-template-columns: 116px minmax(0, 1fr) auto;
  gap: 4px 24px;
  align-items: center;
  padding: 16px 20px 16px 22px;
  border-top: 1px solid var(--line);
  transition: background-color .12s;
}
.ad:first-child { border-top: 0; }
.ad:hover { background: var(--surface-hover); }
.ad.is-new::before {
  content: "";
  position: absolute;
  left: 0; top: 12px; bottom: 12px;
  width: 4px;
  border-radius: 0 3px 3px 0;
  background: var(--blaze);
}
.when { display: flex; flex-direction: column; line-height: 1.25; }
.when .rel { font-weight: 600; font-size: .95rem; }
.when .abs { font-size: .8rem; color: var(--faint); font-variant-numeric: tabular-nums; }
.new-tag { color: var(--blaze); font-weight: 600; font-size: .8rem; }

.body { min-width: 0; }
.title { margin: 0 0 3px; font-size: 1.05rem; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.title a { text-decoration: none; }
.title a::after { content: ""; position: absolute; inset: 0; }
.title a:focus-visible { outline: none; }
.ad:has(.title a:focus-visible) { outline: 2px solid var(--focus); outline-offset: -2px; }
.ad:hover .title a { text-decoration: underline; text-decoration-color: var(--faint); text-underline-offset: 3px; }
.where { display: inline-flex; align-items: center; gap: 5px; font-size: .9rem; color: var(--muted); }
.where svg { flex: none; }
mark { background: var(--blaze-soft); color: inherit; border-radius: 2px; box-shadow: inset 0 -2px 0 var(--blaze); }

.price {
  font-family: var(--font-cond);
  font-weight: 600;
  font-size: 1.6rem;
  line-height: 1;
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.price.none { font-family: var(--font); font-size: .9rem; font-weight: 500; color: var(--faint); }

.empty {
  padding: 56px 24px;
  text-align: center;
  border: 1px dashed var(--line);
  border-radius: var(--radius);
  color: var(--muted);
}
.empty strong { display: block; color: var(--ink); font-size: 1.1rem; margin-bottom: 4px; }
.empty p { margin: 0 0 12px; }

footer {
  max-width: 1240px;
  margin: 0 auto;
  padding: 20px 24px 40px;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px 24px;
  font-size: .85rem;
  color: var(--muted);
  border-top: 1px solid var(--line);
}
footer a { color: var(--muted); text-underline-offset: 3px; }
footer a:hover { color: var(--ink); }

/* ---------- Tablet / mobil ---------- */
@media (max-width: 900px) {
  .layout { grid-template-columns: minmax(0, 1fr); gap: 12px; padding-top: 16px; }
  .filters { position: static; }
  .filters-toggle {
    display: inline-flex; align-items: center; gap: 8px;
    font: inherit; font-weight: 600; color: var(--ink);
    background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
    padding: 9px 14px; cursor: pointer;
  }
  .filters-toggle .count-pill {
    background: var(--blaze); color: #fff; font-size: .75rem; font-weight: 700;
    border-radius: 999px; min-width: 20px; padding: 1px 6px; text-align: center;
  }
  .filters-body {
    display: none;
    margin-top: 10px;
    padding: 18px 18px 4px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius);
  }
  .filters.open .filters-body { display: block; }
}
@media (max-width: 620px) {
  .masthead-inner { padding: 32px 16px 26px; }
  .layout { padding: 12px 16px 48px; }
  .tally { gap: 22px; }
  .tally dd { font-size: 1.8rem; }
  .search kbd { display: none; }
  .ad {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas: "when price" "body body";
    gap: 6px 12px;
    padding: 14px 16px 14px 18px;
  }
  .when { grid-area: when; flex-direction: row; flex-wrap: wrap; gap: 0 8px; align-items: baseline; }
  .body { grid-area: body; }
  .price { grid-area: price; font-size: 1.4rem; }
  footer { padding: 20px 16px 32px; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
</style>
</head>
<body data-generated="%%GEN_MS%%">

<header class="masthead">
  <div class="masthead-inner">
    <div>
      <h1>Hunting Bazar</h1>
      <p class="lede">Zbraně z bazaru hunting-shop.cz vložené od %%START%% do %%END%%.</p>
    </div>
    <dl class="tally">
      <div><dt>inzerátů</dt><dd>%%COUNT%%</dd></div>
      <div class="is-blaze"><dt>nových za 24 h</dt><dd>%%NEW%%</dd></div>
      <div><dt>medián ceny</dt><dd>%%MEDIAN%%</dd></div>
    </dl>
  </div>
</header>

<div class="layout">
  <aside class="filters js-only" id="filters">
    <button type="button" class="filters-toggle" id="filtersToggle" aria-expanded="false" aria-controls="filtersBody">
      %%FILTER_ICON%% Filtry <span class="count-pill" id="activeCount" hidden>0</span>
    </button>
    <div class="filters-body" id="filtersBody">
      <div class="filter-group">
        <label class="filter-label" for="loc">Lokalita</label>
        <select id="loc">
          <option value="all">Všechny lokality</option>
          %%LOC_OPTIONS%%
        </select>
      </div>
      <div class="filter-group">
        <span class="filter-label">Cena v Kč</span>
        <div class="pair">
          <input type="number" id="pmin" min="0" step="100" inputmode="numeric" placeholder="od" aria-label="Cena od">
          <input type="number" id="pmax" min="0" step="100" inputmode="numeric" placeholder="do" aria-label="Cena do">
        </div>
        <label class="check"><input type="checkbox" id="hideNoPrice"> Skrýt inzeráty bez ceny</label>
      </div>
      <div class="filter-group">
        <span class="filter-label">Vloženo</span>
        <div class="chips" id="periodChips">
          <button type="button" class="chip" data-period="all" aria-pressed="true">Kdykoli</button>
          <button type="button" class="chip" data-period="24" aria-pressed="false">Za 24 h</button>
          <button type="button" class="chip" data-period="72" aria-pressed="false">Za 3 dny</button>
        </div>
        <details>
          <summary>Vlastní rozsah</summary>
          <div class="stack">
            <input type="datetime-local" id="dfrom" aria-label="Vloženo od">
            <input type="datetime-local" id="dto" aria-label="Vloženo do">
          </div>
        </details>
      </div>
      <div class="filter-group">
        <button type="button" class="btn-text" id="reset">Zrušit všechny filtry</button>
      </div>
    </div>
  </aside>

  <main>
    <div class="toolbar js-only">
      <div class="search">
        %%SEARCH_ICON%%
        <input type="search" id="q" placeholder="Hledat v názvu, třeba Blaser nebo Tikka" autocomplete="off" aria-label="Hledat v názvu">
        <kbd>/</kbd>
      </div>
      <div class="seg" role="group" aria-label="Řazení">
        <button type="button" data-sort="new" aria-pressed="true">Nejnovější</button>
        <button type="button" data-sort="old" aria-pressed="false">Nejstarší</button>
        <button type="button" data-sort="cheap" aria-pressed="false">Nejlevnější</button>
        <button type="button" data-sort="exp" aria-pressed="false">Nejdražší</button>
      </div>
    </div>
    <div class="status js-only"><span id="count" aria-live="polite"></span></div>

    <ul class="list" id="list"%%LIST_HIDDEN%%>
%%ROWS%%
    </ul>

    <div class="empty" id="empty"%%EMPTY_HIDDEN%%>
      <strong id="emptyTitle">%%EMPTY_TITLE%%</strong>
      <p id="emptyText">%%EMPTY_TEXT%%</p>
      <button type="button" class="btn-text js-only" id="reset2">Zrušit všechny filtry</button>
    </div>
  </main>
</div>

<footer>
  <span>Vygenerováno %%GEN_TIME%%</span>
  <a href="https://app.krystofklika.cz" target="_blank" rel="noopener noreferrer">Autor: Kryštof Klika</a>
</footer>

<script>
(() => {
  const $ = (id) => document.getElementById(id);
  const GEN = Number(document.body.dataset.generated);
  const fold = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const pad = (n) => String(n).padStart(2, '0');
  const list = $('list');

  // Načtení inzerátů z vyrenderovaného HTML
  const items = [...list.querySelectorAll('.ad')].map((el) => {
    const a = el.querySelector('.title a');
    const title = a.textContent;
    let folded = '';
    const map = [];
    for (let i = 0; i < title.length; i++) {
      const f = fold(title[i]);
      for (let k = 0; k < f.length; k++) { folded += f[k]; map.push(i); }
    }
    return {
      el, a, title, folded, map,
      ts: Number(el.dataset.ts),
      price: el.dataset.price === '' ? null : Number(el.dataset.price),
      loc: el.dataset.loc,
      rel: el.querySelector('.rel'),
      highlighted: false,
    };
  });

  const state = { period: 'all', sort: 'new' };

  // Relativní čas ("před 12 min", "včera 18:40")
  function relTime(ts) {
    const d = new Date(ts);
    const hm = pad(d.getHours()) + ':' + pad(d.getMinutes());
    const diffMin = Math.floor((Date.now() - ts) / 60000);
    if (diffMin >= 0 && diffMin < 1) return 'právě teď';
    if (diffMin >= 1 && diffMin < 60) return 'před ' + diffMin + ' min';
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const t0 = today.getTime();
    if (ts >= t0 && ts < t0 + 864e5) return 'dnes ' + hm;
    if (ts >= t0 - 864e5 && ts < t0) return 'včera ' + hm;
    return d.getDate() + '. ' + (d.getMonth() + 1) + '. ' + hm;
  }
  function refreshTimes() { for (const it of items) it.rel.textContent = relTime(it.ts); }

  // Zvýraznění hledaného textu – jen přes textové uzly, žádné innerHTML
  function highlight(it, q) {
    if (!q) {
      if (it.highlighted) { it.a.textContent = it.title; it.highlighted = false; }
      return;
    }
    const { a, title, folded, map } = it;
    a.textContent = '';
    let last = 0, from = 0, idx;
    while ((idx = folded.indexOf(q, from)) !== -1) {
      const s = map[idx], e = map[idx + q.length - 1] + 1;
      if (s > last) a.append(title.slice(last, s));
      const m = document.createElement('mark');
      m.textContent = title.slice(s, e);
      a.append(m);
      last = e;
      from = idx + q.length;
    }
    if (last < title.length) a.append(title.slice(last));
    it.highlighted = true;
  }

  const num = (id) => { const v = $(id).value.trim(); return v === '' ? null : Number(v); };
  const dt = (id) => ($(id).value ? new Date($(id).value).getTime() : null);

  function apply() {
    const q = fold($('q').value.trim());
    const loc = $('loc').value;
    const hide = $('hideNoPrice').checked;
    const pmin = num('pmin'), pmax = num('pmax');
    const from = dt('dfrom'), to = dt('dto');
    const since = state.period === 'all' ? null : GEN - Number(state.period) * 3600e3;

    let shown = 0;
    for (const it of items) {
      const ok = (!q || it.folded.includes(q))
        && (loc === 'all' || it.loc === loc)
        && (it.price === null ? !hide : (pmin === null || it.price >= pmin) && (pmax === null || it.price <= pmax))
        && (since === null || it.ts >= since)
        && (from === null || it.ts >= from)
        && (to === null || it.ts <= to);
      it.el.hidden = !ok;
      if (ok) { shown++; highlight(it, q); }
    }

    const active = [q, loc !== 'all', pmin !== null, pmax !== null, hide,
      state.period !== 'all', from !== null, to !== null].filter(Boolean).length;
    $('activeCount').textContent = active;
    $('activeCount').hidden = active === 0;

    if (items.length) {
      $('count').textContent = shown === items.length
        ? 'Zobrazeny všechny inzeráty (' + items.length + ')'
        : 'Zobrazeno ' + shown + ' z ' + items.length;
      list.hidden = shown === 0;
      $('empty').hidden = shown !== 0;
      if (shown === 0) {
        $('emptyTitle').textContent = 'Filtrům neodpovídá žádný inzerát';
        $('emptyText').textContent = 'Uvolni cenové rozpětí nebo zkus kratší hledaný výraz.';
        $('reset2').hidden = false;
      }
    } else {
      $('reset2').hidden = true;
    }
  }

  const byPrice = (dir) => (a, b) =>
    (a.price === null) - (b.price === null)
    || (a.price === null ? b.ts - a.ts : dir * (a.price - b.price))
    || b.ts - a.ts;
  const comparators = {
    new: (a, b) => b.ts - a.ts,
    old: (a, b) => a.ts - b.ts,
    cheap: byPrice(1),
    exp: byPrice(-1),
  };
  function sortList() {
    items.sort(comparators[state.sort]);
    list.append(...items.map((it) => it.el));
  }

  function setPressed(container, attr, value) {
    container.querySelectorAll('[data-' + attr + ']').forEach((b) =>
      b.setAttribute('aria-pressed', String(b.dataset[attr] === value)));
  }

  function reset() {
    ['q', 'pmin', 'pmax', 'dfrom', 'dto'].forEach((id) => { $(id).value = ''; });
    $('loc').value = 'all';
    $('hideNoPrice').checked = false;
    state.period = 'all';
    setPressed($('periodChips'), 'period', 'all');
    apply();
  }

  // Události
  ['q', 'pmin', 'pmax', 'dfrom', 'dto'].forEach((id) => $(id).addEventListener('input', apply));
  $('loc').addEventListener('change', apply);
  $('hideNoPrice').addEventListener('change', apply);
  $('reset').addEventListener('click', reset);
  $('reset2').addEventListener('click', reset);

  $('periodChips').addEventListener('click', (e) => {
    const b = e.target.closest('[data-period]');
    if (!b) return;
    state.period = b.dataset.period;
    setPressed($('periodChips'), 'period', state.period);
    apply();
  });

  const seg = document.querySelector('.seg');
  seg.addEventListener('click', (e) => {
    const b = e.target.closest('[data-sort]');
    if (!b) return;
    state.sort = b.dataset.sort;
    setPressed(seg, 'sort', state.sort);
    sortList();
  });

  $('filtersToggle').addEventListener('click', () => {
    const open = $('filters').classList.toggle('open');
    $('filtersToggle').setAttribute('aria-expanded', String(open));
  });

  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (e.key === '/' && !['input', 'select', 'textarea'].includes(tag)) {
      e.preventDefault();
      $('q').focus();
    } else if (e.key === 'Escape' && e.target === $('q') && $('q').value) {
      $('q').value = '';
      apply();
    }
  });

  refreshTimes();
  setInterval(refreshTimes, 60000);
  sortList();
  apply();
})();
</script>
</body>
</html>
"""


def generate_html(ads):
    now = datetime.now()
    current_date_str = now.strftime('%d. %m. %Y')
    generation_time_str = now.strftime('%d. %m. %Y v %H:%M')
    threshold_date_str = (now - timedelta(days=DAYS_BACK)).strftime('%d. %m. %Y')

    rows = []
    prices = []
    new_count = 0

    for ad in ads:
        dt = datetime.strptime(f"{ad['date']} {ad['time']}", '%d. %m. %Y %H:%M:%S')
        ts_ms = int(dt.timestamp() * 1000)
        price_num = parse_price(ad['price'])
        if price_num is not None:
            prices.append(price_num)

        is_new = timedelta(0) <= (now - dt) <= timedelta(hours=24)
        if is_new:
            new_count += 1

        abs_text = dt.strftime('%d. %m. %Y, %H:%M')
        date_only = dt.strftime('%d. %m. %Y')
        price_html = format_price(ad['price'], price_num)
        price_class = "price" if price_num is not None else "price none"
        new_tag = '<span class="new-tag">nové</span>' if is_new else ''

        rows.append(
            f'      <li class="ad{" is-new" if is_new else ""}" data-ts="{ts_ms}" '
            f'data-price="{"" if price_num is None else price_num}" data-loc="{esc(ad["location"])}">\n'
            f'        <time class="when" datetime="{dt.isoformat()}" title="{esc(ad["date"])}, {esc(ad["time"])}">'
            f'<span class="rel">{esc(abs_text)}</span>'
            f'<span class="abs">{esc(date_only)}</span>{new_tag}</time>\n'
            f'        <div class="body">\n'
            f'          <h2 class="title"><a href="{esc(safe_link(ad["link"]))}" target="_blank" rel="noopener noreferrer">{esc(ad["title"])}</a></h2>\n'
            f'          <span class="where">{PIN_ICON}{esc(ad["location"])}</span>\n'
            f'        </div>\n'
            f'        <div class="{price_class}">{esc(price_html)}</div>\n'
            f'      </li>'
        )

    loc_counts = Counter(ad['location'] for ad in ads)
    location_options = "\n          ".join(
        f'<option value="{esc(loc)}">{esc(loc)} ({n})</option>'
        for loc, n in sorted(loc_counts.items(), key=lambda kv: sort_key_cs(kv[0]))
    )

    median_str = format_czk(int(round(statistics.median(prices)))) if prices else "–"

    replacements = {
        "%%START%%": esc(threshold_date_str),
        "%%END%%": esc(current_date_str),
        "%%GEN_TIME%%": esc(generation_time_str),
        "%%GEN_MS%%": str(int(now.timestamp() * 1000)),
        "%%COUNT%%": str(len(ads)),
        "%%NEW%%": str(new_count),
        "%%MEDIAN%%": esc(median_str),
        "%%LOC_OPTIONS%%": location_options,
        "%%ROWS%%": "\n".join(rows),
        "%%LIST_HIDDEN%%": "" if ads else " hidden",
        "%%EMPTY_HIDDEN%%": " hidden" if ads else "",
        "%%EMPTY_TITLE%%": "Žádné nové inzeráty",
        "%%EMPTY_TEXT%%": esc(f"Za posledních {DAYS_BACK} dní se v bazaru nic neobjevilo. Další kontrola proběhne při příštím spuštění skriptu."),
        "%%SEARCH_ICON%%": SEARCH_ICON,
        "%%FILTER_ICON%%": FILTER_ICON,
    }

    final_output = HTML_TEMPLATE
    for key, value in replacements.items():
        final_output = final_output.replace(key, value)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_output)

    print(f"HTML dashboard úspěšně aktualizován: {OUTPUT_FILE}")

    if SEND_EMAIL:
        send_email(final_output)
    if UPLOAD_TO_FTP:
        upload_to_ftp(final_output)


if __name__ == "__main__":
    scrape_hunting_bazar()
