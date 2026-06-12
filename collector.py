"""
Sottosuoli — RSS Collector
Scarica articoli dalle ultime 24h, filtra per keyword, aggiorna index.html
"""

import feedparser
import json
import re
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# === CONFIGURAZIONE FEED ===
FEEDS = [
    # Istituzionali italiane
    {"url": "https://www.isprambiente.gov.it/it/feed/news.xml",         "fonte": "ISPRA",            "categoria": "istituzionale"},
    {"url": "https://www.arpa.veneto.it/rss/news.xml",                  "fonte": "ARPA Veneto",      "categoria": "istituzionale"},
    {"url": "https://www.protezionecivile.gov.it/it/feed/news.xml",     "fonte": "Protezione Civile","categoria": "istituzionale"},
    # Europee / internazionali
    {"url": "https://www.eea.europa.eu/en/newsroom/news/RSS",           "fonte": "EEA",              "categoria": "europea"},
    {"url": "https://joint-research-centre.ec.europa.eu/rss.xml",      "fonte": "JRC",              "categoria": "europea"},
    {"url": "https://climate.copernicus.eu/rss.xml",                    "fonte": "Copernicus",       "categoria": "europea"},
    # Testate giornalistiche
    {"url": "https://www.ilbovivo.it/feed/",                            "fonte": "Il Bo Live",       "categoria": "giornalismo"},
    {"url": "https://www.nuovavenezia.it/rss/home.xml",                 "fonte": "La Nuova Venezia", "categoria": "giornalismo"},
    {"url": "https://www.corrieredelveneto.it/rss/home.xml",            "fonte": "Corriere Veneto",  "categoria": "giornalismo"},
    {"url": "https://www.meteoweb.eu/feed/",                            "fonte": "MeteoWeb",         "categoria": "giornalismo"},
]

# === KEYWORD PER CATEGORIA TEMATICA ===
KEYWORDS = {
    "rischio_idrogeologico": [
        "alluvione", "alluvioni", "esondazione", "frana", "frane",
        "idrogeologico", "dissesto", "subsidenza", "inondazione",
        "rischio idraulico", "piano di bacino", "pai", "protezione civile",
        "emergenza meteo", "maltempo", "nubifragio",
    ],
    "clima_estremo": [
        "cambiamenti climatici", "clima", "siccità", "caldo estremo",
        "ondata di calore", "temperatura record", "precipitazioni intense",
        "evento estremo", "adattamento climatico", "resilienza",
        "cop", "ipcc", "emissioni", "co2", "decarbonizzazione",
        "ghiacciai", "innalzamento del mare", "sea level",
    ],
    "consumo_suolo": [
        "consumo di suolo", "impermeabilizzazione", "urbanizzazione",
        "cementificazione", "rigenerazione urbana", "sprawl",
        "verde urbano", "aree naturali", "biodiversità",
        "vnr", "snpa",
    ],
}

# Tutte le keyword unite per il filtro rapido
ALL_KEYWORDS = [kw for kws in KEYWORDS.values() for kw in kws]

# === PARAMETRI ===
MAX_AGE_HOURS = 48       # articoli più vecchi di N ore vengono scartati
MAX_ITEMS_OUTPUT = 5     # quanti articoli mostrare sul sito
OUTPUT_JSON = "sottosuoli_news.json"
INDEX_HTML = "index.html"


def normalize(text: str) -> str:
    """Minuscolo e rimozione punteggiatura per matching keyword."""
    return text.lower() if text else ""


def match_keywords(title: str, summary: str) -> list[str]:
    """Restituisce le categorie tematiche che matchano il testo."""
    text = normalize(title + " " + summary)
    matched = []
    for categoria, kws in KEYWORDS.items():
        if any(kw in text for kw in kws):
            matched.append(categoria)
    return matched


def parse_date(entry) -> datetime | None:
    """Prova a estrarre una data pubblicazione dall'entry feedparser."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_feed(feed_config: dict) -> list[dict]:
    """Scarica e processa un singolo feed RSS."""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    try:
        parsed = feedparser.parse(feed_config["url"])
        if parsed.bozo and not parsed.entries:
            print(f"  ⚠️  {feed_config['fonte']}: feed non raggiungibile o malformato")
            return items

        for entry in parsed.entries:
            title   = getattr(entry, "title", "").strip()
            summary = getattr(entry, "summary", "").strip()
            link    = getattr(entry, "link", "")
            pub     = parse_date(entry)

            # Salta se troppo vecchio
            if pub and pub < cutoff:
                continue

            # Salta se nessuna keyword corrisponde
            categorie = match_keywords(title, summary)
            if not categorie:
                continue

            # Pulisce il summary da tag HTML
            summary_clean = re.sub(r"<[^>]+>", "", summary)[:280]

            items.append({
                "titolo":    title,
                "sommario":  summary_clean,
                "link":      link,
                "fonte":     feed_config["fonte"],
                "categoria_fonte": feed_config["categoria"],
                "temi":      categorie,
                "data":      pub.strftime("%d %b %Y") if pub else "data n/d",
                "data_iso":  pub.isoformat() if pub else "",
            })

        print(f"  ✅ {feed_config['fonte']}: {len(items)} articoli trovati")

    except Exception as e:
        print(f"  ❌ {feed_config['fonte']}: errore — {e}")

    return items


def tema_label(temi: list[str]) -> str:
    """Converte chiavi interne in etichette leggibili."""
    labels = {
        "rischio_idrogeologico": "Rischio idrogeologico",
        "clima_estremo":         "Clima estremo",
        "consumo_suolo":         "Consumo di suolo",
    }
    return " · ".join(labels.get(t, t) for t in temi)


def update_html(items: list[dict], html_path: str):
    """Aggiorna il blocco notizie in index.html."""
    if not Path(html_path).exists():
        print(f"  ⚠️  {html_path} non trovato, salto aggiornamento HTML")
        return

    # Costruisce il blocco HTML notizie
    if not items:
        news_html = '<div class="news-placeholder">Nessuna notizia nelle ultime 48 ore. Riprova domani.</div>'
    else:
        parts = []
        for item in items[:MAX_ITEMS_OUTPUT]:
            temi_str = tema_label(item["temi"])
            title_esc = item["titolo"].replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"""      <a class="news-item" href="{item['link']}" target="_blank" style="text-decoration:none;display:block;">
        <div class="news-tag">{temi_str} · {item['fonte']}</div>
        <div class="news-title">{title_esc}</div>
        <div class="news-date">{item['data']}</div>
      </a>""")
        news_html = "\n".join(parts)

    # Sostituisce il contenuto tra i marker nel HTML
    html = Path(html_path).read_text(encoding="utf-8")
    marker_start = '<!-- SOTTOSUOLI:START -->'
    marker_end   = '<!-- SOTTOSUOLI:END -->'

    new_block = f"{marker_start}\n{news_html}\n      {marker_end}"

    if marker_start in html:
        html = re.sub(
            rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}",
            new_block,
            html,
            flags=re.DOTALL,
        )
        print(f"  ✅ index.html aggiornato con {min(len(items), MAX_ITEMS_OUTPUT)} notizie")
    else:
        print(f"  ⚠️  Marker SOTTOSUOLI non trovato in {html_path} — aggiunta manuale necessaria")

    Path(html_path).write_text(html, encoding="utf-8")


def main():
    print(f"\n🌍 Sottosuoli Collector — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 50)

    all_items = []
    for feed in FEEDS:
        print(f"\n📡 {feed['fonte']} ({feed['categoria']})")
        items = fetch_feed(feed)
        all_items.extend(items)

    # Deduplicazione per URL
    seen = set()
    unique = []
    for item in all_items:
        if item["link"] not in seen:
            seen.add(item["link"])
            unique.append(item)

    # Ordina per data decrescente
    unique.sort(key=lambda x: x["data_iso"], reverse=True)

    print(f"\n📊 Totale articoli unici trovati: {len(unique)}")

    # Salva JSON completo
    output = {
        "aggiornato": datetime.now(timezone.utc).isoformat(),
        "totale": len(unique),
        "articoli": unique,
    }
    Path(OUTPUT_JSON).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 Salvato {OUTPUT_JSON}")

    # Aggiorna HTML
    update_html(unique, INDEX_HTML)

    print("\n✅ Done.\n")


if __name__ == "__main__":
    main()
