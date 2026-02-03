import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import time
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# KONFIGURACE
DAYS_BACK = 2
BASE_URL = "https://bazar.hunting-shop.cz/sekce/51-bazar-zbrane/"
OUTPUT_FILE = "vysledek_inzeraty.html"

# KONFIGURACE SMTP (Port 587, TLS)
SMTP_SERVER = "smtp.protonmail.ch"
SMTP_PORT = 587
SMTP_USER = "odesilatel@domena.cz"
SMTP_PASSWORD = "heslo"
EMAIL_TO = "prijemce@domena.cz"
SEND_EMAIL = False  # Přepni na False, pokud chceš jen generovat soubor. True, pokud chceš výsledek posílat emailem.

# Legitimní hlavičky prohlížeče pro obejití 403
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    "Referer": "https://bazar.hunting-shop.cz/"
}

def send_email(html_content):
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = f"Hunting Bazar: Nové inzeráty za poslední {DAYS_BACK} dny"

    msg.attach(MIMEText(html_content, 'html'))
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {OUTPUT_FILE}",
        )
        msg.attach(part)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Aktivace TLS
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

    # Použití Session pro udržení cookies (vypadá to přirozeněji)
    session = requests.Session()
    session.headers.update(HEADERS)

    while continue_scraping:
        params = {
            'filtr': 'n',
            'list': page,
            'search': ''
        }
        
        try:
            response = session.get(BASE_URL, params=params, timeout=10)
            
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
                
                date_match = re.search(r'(\d{2}\. \d{2}\. \d{4})', date_span.text)
                if not date_match:
                    continue
                
                ad_date = datetime.strptime(date_match.group(1), '%d. %m. %Y')
                
                if ad_date < threshold_date:
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
                    'date': date_match.group(1),
                    'link': link
                })
            
            print(f"Stránka {page} hotova...")
            page += 1
            time.sleep(1.5)
            
        except Exception as e:
            print(f"Chyba: {e}")
            break

    generate_html(all_ads)

def generate_html(ads):
    # Příprava dat pro hlavičku
    current_date_str = datetime.now().strftime('%d. %m. %Y')
    threshold_date_str = (datetime.now() - timedelta(days=DAYS_BACK)).strftime('%d. %m. %Y')
    
    # Unikátní seznam míst pro filtr
    locations = sorted(list(set(ad['location'] for ad in ads)))
    location_options = "".join([f'<option value="{loc}">{loc}</option>' for loc in locations])

    html_template = """
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8">
        <title>Hunting Bazar Scraper</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f0f2f0; padding: 20px; color: #333; }}
            .container {{ max-width: 1100px; margin: auto; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            
            .header-info {{ text-align: center; border-bottom: 3px solid #7D8873; padding-bottom: 15px; margin-bottom: 20px; }}
            h2 {{ color: #2F2D14; margin: 0 0 5px 0; }}
            .date-range {{ color: #555; font-style: italic; font-size: 1.1em; }}
            
            .controls {{ display: flex; gap: 20px; margin-bottom: 20px; background: #f9f9f9; padding: 15px; border-radius: 8px; align-items: center; justify-content: center; border: 1px solid #eee; }}
            select, button {{ padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; background: white; }}
            button {{ background: #7D8873; color: white; border: none; font-weight: bold; transition: 0.2s; }}
            button:hover {{ background: #5d6656; }}

            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px 15px; border-bottom: 1px solid #eee; text-align: left; }}
            th {{ background-color: #2F2D14; color: white; cursor: pointer; transition: 0.2s; }}
            th:hover {{ background-color: #45421d; }}
            
            tr:hover {{ background-color: #fcfcfc; }}
            .price-val {{ font-weight: bold; color: #2c3e50; }}
            .date {{ color: #666; font-size: 0.9em; }}
            a {{ color: #7D8873; text-decoration: none; font-weight: bold; }}
            a:hover {{ text-decoration: underline; }}
            
            .stats {{ margin-top: 15px; font-size: 0.9em; color: #888; text-align: right; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-info">
                <h2>Nové inzeráty z Hunting Bazaru</h2>
                <div class="date-range">Zahrnuté období: <strong>{start}</strong> až <strong>{end}</strong></div>
            </div>
            
            <div class="controls">
                <div>
                    <strong>Filtr místa: </strong>
                    <select id="locationFilter" onchange="filterTable()">
                        <option value="all">Všechny regiony</option>
                        {location_options}
                    </select>
                </div>
                <div>
                    <strong>Rychlé řazení ceny: </strong>
                    <button onclick="sortTable(3, 'asc')">Nejlevnější</button>
                    <button onclick="sortTable(3, 'desc')">Nejdražší</button>
                </div>
            </div>

            <table id="adTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0, 'desc')" title="Klikněte pro seřazení">Datum</th>
                        <th>Inzerát (název a odkaz)</th>
                        <th>Místo prodeje</th>
                        <th onclick="sortTable(3, 'asc')" title="Klikněte pro seřazení">Cena</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                    {rows}
                </tbody>
            </table>
            <div class="stats">Celkem nalezeno inzerátů: {count}</div>
        </div>

        <script>
            function filterTable() {{
                const filter = document.getElementById('locationFilter').value;
                const rows = document.getElementById('tableBody').getElementsByTagName('tr');
                
                for (let row of rows) {{
                    const location = row.getElementsByTagName('td')[2].textContent;
                    row.style.display = (filter === 'all' || location === filter) ? "" : "none";
                }}
            }}

            function sortTable(colIndex, dir) {{
                const tbody = document.getElementById("tableBody");
                const rows = Array.from(tbody.rows);

                const sortedRows = rows.sort((a, b) => {{
                    let valA = a.cells[colIndex].textContent.trim();
                    let valB = b.cells[colIndex].textContent.trim();

                    if (colIndex === 3) {{
                        valA = parseInt(valA.replace(/\D/g, '')) || 0;
                        valB = parseInt(valB.replace(/\D/g, '')) || 0;
                    }}
                    
                    if (colIndex === 0) {{
                        // Převod českého datumu na porovnatelný formát
                        valA = valA.split('. ').reverse().join('-');
                        valB = valB.split('. ').reverse().join('-');
                    }}

                    if (dir === 'asc') return valA > valB ? 1 : -1;
                    return valA < valB ? 1 : -1;
                }});

                while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
                tbody.append(...sortedRows);
            }}
        </script>
    </body>
    </html>
    """
    
    rows = ""
    for ad in ads:
        rows += f"""
        <tr>
            <td class="date">{ad['date']}</td>
            <td><a href="{ad['link']}" target="_blank">{ad['title']}</a></td>
            <td>{ad['location']}</td>
            <td class="price-val">{ad['price']}</td>
        </tr>
        """
    
    final_output = html_template.format(
        start=threshold_date_str, 
        end=current_date_str, 
        location_options=location_options, 
        rows=rows,
        count=len(ads)
    )
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_output)
    print(f"Výsledek byl úspěšně vygenerován do souboru: {OUTPUT_FILE}")

    if SEND_EMAIL:
        send_email(final_output)    

if __name__ == "__main__":
    scrape_hunting_bazar()
