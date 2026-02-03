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
import ftplib
import io

from data import SMTP_PASSWORD, SMTP_PORT, SMTP_SERVER, SMTP_USER, FTP_HOST, FTP_PASS, FTP_PATH, FTP_USER, EMAIL_TO

# KONFIGURACE
DAYS_BACK = 7
BASE_URL = "https://bazar.hunting-shop.cz/sekce/51-bazar-zbrane/"
OUTPUT_FILE = "inzeraty.html"

SEND_EMAIL = False  # Přepni na False, pokud chceš jen generovat soubor. True, pokud chceš výsledek posílat emailem.
UPLOAD_TO_FTP = True

# Legitimní hlavičky prohlížeče pro obejití 403
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    "Referer": "https://bazar.hunting-shop.cz/"
}

def upload_to_ftp(html_content):
    try:
        # Použijeme io.BytesIO, abychom nemuseli soubor znovu číst z disku
        bio = io.BytesIO(html_content.encode('utf-8'))
        
        with ftplib.FTP(FTP_HOST) as ftp:
            ftp.login(user=FTP_USER, passwd=FTP_PASS)
            # Přepnutí do pasivního režimu (obvykle nutné pro servery za firewallem)
            ftp.set_pasv(True)
            
            # Nahrání souboru
            ftp.storbinary(f"STOR {FTP_PATH}", bio)
            
        print(f"Soubor byl úspěšně nahrán na FTP: {FTP_HOST}")
    except Exception as e:
        print(f"Chyba při nahrávání na FTP: {e}")

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
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {OUTPUT_FILE}",
        )
        msg.attach(part)
        msg.attach(MIMEText("V příloze nalezneš výpis inzerátů.", 'html'))
    else:
        msg.attach(MIMEText(html_content, 'html'))

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
                
                # Upravený regex pro zachycení data i času
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
            time.sleep(1.5) # Pauza, aby nás server hned nezařízl
            
        except Exception as e:
            print(f"Chyba: {e}")
            break

    generate_html(all_ads)

def generate_html(ads):
    # Příprava dat pro hlavičku
    now = datetime.now()
    current_date_str = now.strftime('%d. %m. %Y')
    generation_time_str = now.strftime('%d. %m. %Y %H:%M')
    threshold_date_str = (now - timedelta(days=DAYS_BACK)).strftime('%d. %m. %Y')
    
    # Získáme unikátní seznam míst pro filtr
    locations = sorted(list(set(ad['location'] for ad in ads)))
    location_options = "".join([f'<option value="{loc}">{loc}</option>' for loc in locations])

    html_template = """
    <!DOCTYPE html>
    <html lang="cs">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hunting Bazar Monitor</title>
        <style>
            :root {{
                --bg: #0f172a;
                --card-bg: #1e293b;
                --text-main: #f1f5f9;
                --text-dim: #94a3b8;
                --accent: #38bdf8;
                --border: #334155;
            }}

            body {{ 
                font-family: 'Inter', -apple-system, sans-serif; 
                background-color: var(--bg); 
                color: var(--text-main);
                margin: 0;
                padding: 40px 20px;
                line-height: 1.5;
            }}

            .container {{ max-width: 1200px; margin: auto; }}
            
            .header {{ 
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
                border-bottom: 1px solid var(--border);
                padding-bottom: 20px;
                margin-bottom: 40px;
            }}

            h2 {{ margin: 0; font-size: 2rem; font-weight: 800; color: var(--accent); }}
            
            .controls {{ 
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                background: var(--card-bg);
                padding: 24px;
                border-radius: 16px;
                margin-bottom: 30px;
                border: 1px solid var(--border);
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
            }}

            .control-group {{ display: flex; flex-direction: column; gap: 8px; }}
            .checkbox-group {{ flex-direction: row; align-items: center; gap: 10px; cursor: pointer; }}
            .checkbox-group input {{ width: auto; cursor: pointer; }}
            label {{ font-size: 0.75rem; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }}

            input, select {{ 
                background: var(--bg);
                border: 1px solid var(--border);
                color: var(--text-main);
                padding: 10px 14px;
                border-radius: 8px;
                font-size: 0.95rem;
                outline: none;
                transition: border-color 0.2s;
            }}

            input:focus, select:focus {{ border-color: var(--accent); }}

            .price-inputs {{ display: flex; gap: 8px; }}
            .price-inputs input {{ width: 100%; }}

            .btn-group {{ display: flex; flex-wrap: wrap; gap: 8px; }}
            .sort-btn {{ 
                flex: 1;
                min-width: 120px;
                padding: 8px;
                background: var(--border);
                border: none;
                border-radius: 8px;
                color: var(--text-main);
                font-size: 0.75rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
                white-space: nowrap;
            }}

            .sort-btn:hover {{ background: var(--accent); color: var(--bg); }}

            .table-container {{
                background: var(--card-bg);
                border-radius: 16px;
                overflow: hidden;
                border: 1px solid var(--border);
            }}

            table {{ width: 100%; border-collapse: collapse; text-align: left; }}
            th {{ 
                background: rgba(15, 23, 42, 0.5);
                padding: 16px;
                font-size: 0.8rem;
                color: var(--text-dim);
                text-transform: uppercase;
                cursor: pointer;
                user-select: none;
            }}
            
            td {{ padding: 16px; border-bottom: 1px solid var(--border); }}
            tr:hover {{ background: rgba(255, 255, 255, 0.02); }}

            .price-val {{ font-weight: 700; color: var(--accent); font-family: 'JetBrains Mono', monospace; }}
            .date {{ color: var(--text-main); font-size: 0.9rem; white-space: nowrap; }}
            .time {{ color: var(--text-dim); font-size: 0.75rem; opacity: 0.7; }}
            
            a {{ color: var(--text-main); text-decoration: none; font-weight: 500; }}
            a:hover {{ color: var(--accent); }}
            
            @media (max-width: 768px) {{
                body {{ padding: 10px; }}
                .header {{ flex-direction: column; align-items: flex-start; gap: 15px; }}
                h2 {{ font-size: 1.5rem; }}
                
                table, thead, tbody, th, td, tr {{ display: block; }}
                thead tr {{ position: absolute; top: -9999px; left: -9999px; }}
                tr {{ border-bottom: 2px solid var(--border); padding: 10px 0; }}
                td {{ 
                    border: none; 
                    position: relative; 
                    padding-left: 35% !important; 
                    text-align: left; 
                    min-height: 30px;
                }}
                td:before {{ 
                    position: absolute; 
                    left: 10px; 
                    width: 30%; 
                    white-space: nowrap; 
                    color: var(--text-dim);
                    font-size: 0.7rem;
                    text-transform: uppercase;
                    font-weight: bold;
                }}
                td:nth-of-type(1):before {{ content: "Datum"; }}
                td:nth-of-type(2):before {{ content: "Inzerát"; }}
                td:nth-of-type(3):before {{ content: "Místo"; }}
                td:nth-of-type(4):before {{ content: "Cena"; }}
                
                .controls {{ grid-template-columns: 1fr; padding: 15px; }}
                .btn-group {{ display: grid; grid-template-columns: 1fr 1fr; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h2>Hunting Bazar</h2>
                    <div style="color: var(--text-dim)">Období: {start} – {end}</div>
                    <div style="color: var(--text-dim); font-size: 0.8rem; margin-top: 5px;">Vygenerováno: {gen_time}</div>
                </div>
                <div style="text-align: right">
                    <div style="font-size: 1.8rem; font-weight: 800; line-height: 1;">{count}</div>
                    <div style="color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-top: 4px;">INZERÁTŮ CELKEM</div>
                </div>
            </div>
            
            <div class="controls">
                <div class="control-group">
                    <label>Hledat v názvu</label>
                    <input type="text" id="searchInput" oninput="applyFilters()" placeholder="Např. Blaser, Tikka...">
                </div>
                <div class="control-group">
                    <label>Lokalita</label>
                    <select id="locationFilter" onchange="applyFilters()">
                        <option value="all">Všechny regiony</option>
                        {location_options}
                    </select>
                </div>
                <div class="control-group">
                    <label>Cena (od - do)</label>
                    <div class="price-inputs">
                        <input type="number" id="priceMin" oninput="applyFilters()" placeholder="Min">
                        <input type="number" id="priceMax" oninput="applyFilters()" placeholder="Max">
                    </div>
                </div>
                <div class="control-group checkbox-group">
                    <input type="checkbox" id="hideNoPrice" onchange="applyFilters()">
                    <label for="hideNoPrice" style="cursor: pointer; text-transform: none;">Skrýt neuvedenou cenu</label>
                </div>
                <div class="control-group">
                    <label>Seřadit výsledky</label>
                    <div class="btn-group">
                        <button class="sort-btn" onclick="sortTable(3, 'asc')">Nejlevnější</button>
                        <button class="sort-btn" onclick="sortTable(3, 'desc')">Nejdražší</button>
                        <button class="sort-btn" onclick="sortTable(0, 'desc')">Nejnovější</button>
                        <button class="sort-btn" onclick="sortTable(0, 'asc')">Nejstarší</button>
                    </div>
                </div>
            </div>

            <div class="table-container">
                <table id="adTable">
                    <thead>
                        <tr>
                            <th onclick="sortTable(0, 'desc')">Datum a čas</th>
                            <th>Inzerát</th>
                            <th>Místo</th>
                            <th onclick="sortTable(3, 'asc')">Cena</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        {rows}
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            function applyFilters() {{
                const locFilter = document.getElementById('locationFilter').value;
                const searchFilter = document.getElementById('searchInput').value.toLowerCase();
                const minPrice = parseInt(document.getElementById('priceMin').value) || 0;
                const maxPrice = parseInt(document.getElementById('priceMax').value) || Infinity;
                const hideNoPrice = document.getElementById('hideNoPrice').checked;
                
                const rows = document.getElementById('tableBody').getElementsByTagName('tr');
                
                for (let row of rows) {{
                    const title = row.getElementsByTagName('td')[1].textContent.toLowerCase();
                    const location = row.getElementsByTagName('td')[2].textContent;
                    const priceText = row.getElementsByTagName('td')[3].textContent;
                    const isNoPrice = priceText.toLowerCase().includes('neuvedena');
                    const priceNum = parseInt(priceText.replace(/[^0-9]/g, '')) || 0;
                    
                    const matchesLoc = (locFilter === 'all' || location === locFilter);
                    const matchesSearch = title.includes(searchFilter);
                    const matchesPrice = isNoPrice ? !hideNoPrice : (priceNum >= minPrice && priceNum <= maxPrice);
                    
                    row.style.display = (matchesLoc && matchesSearch && matchesPrice) ? "" : "none";
                }}
            }}

            function sortTable(colIndex, dir) {{
                const tbody = document.getElementById("tableBody");
                const rows = Array.from(tbody.rows);
                const sortedRows = rows.sort((a, b) => {{
                    let valA = a.cells[colIndex].innerText.trim();
                    let valB = b.cells[colIndex].innerText.trim();

                    if (colIndex === 3) {{
                        valA = parseInt(valA.replace(/[^0-9]/g, '')) || 0;
                        valB = parseInt(valB.replace(/[^0-9]/g, '')) || 0;
                    }}
                    if (colIndex === 0) {{
                        const parseDateTime = (s) => {{
                            const parts = s.split(' ');
                            const dateParts = parts[0].split('.');
                            return dateParts[2] + dateParts[1] + dateParts[0] + parts[1];
                        }};
                        valA = parseDateTime(valA);
                        valB = parseDateTime(valB);
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
            <td class="date">{ad['date']} <span class="time">{ad['time']}</span></td>
            <td><a href="{ad['link']}" target="_blank">{ad['title']}</a></td>
            <td style="color: var(--text-dim);">{ad['location']}</td>
            <td class="price-val">{ad['price']}</td>
        </tr>
        """
    
    final_output = html_template.format(
        start=threshold_date_str, 
        end=current_date_str, 
        gen_time=generation_time_str,
        location_options=location_options, 
        rows=rows,
        count=len(ads)
    )
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_output)
    
    print(f"HTML dashboard úspěšně aktualizován: {OUTPUT_FILE}")

    if SEND_EMAIL:
        send_email(final_output)  
    if UPLOAD_TO_FTP:
        upload_to_ftp(final_output)

if __name__ == "__main__":
    scrape_hunting_bazar()