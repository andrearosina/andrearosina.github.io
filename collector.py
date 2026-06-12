"""
Sottosuoli — RSS Collector v2
Raccoglie articoli da feed RSS, filtra per keyword tematiche, aggiorna index.html
"""

import feedparser
import json
import re
import requests
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
from urllib.parse import urlparse

# === CONFIGURAZIONE FEED ===
# Nota: verifica periodicamente che gli URL siano ancora attivi
FEEDS = [
    # Istituzionali italiane — verificati funzionanti
    {"url": "http://www.isprambiente.gov.it/it/news/notizie/RSS",         "fonte": "ISPRA",               "categoria": "istituzionale"},
    {"url": "https://www.snpambiente.it/feed/",                            "fonte": "SNPA",                "categoria": "istituzionale"},
    {"url": "https://www.cmcc.it/feed",                                    "fonte": "CMCC",                "categoria": "istituzionale"},
    # Europee / internazionali
    {"url": "https://www.copernicus.eu/en/rss.xml",                       "fonte": "Copernicus",          "categoria": "europea"},
    # Testate / divulgazione — verificati funzionanti
    {"url": "https://www.meteoweb.eu/feed/",                              "fonte": "MeteoWeb",            "categoria": "giornalismo"},
    {"url": "https://www.lifegate.it/feed",                               "fonte": "LifeGate",            "categoria": "giornalismo"},
    {"url": "https://www.repubblica.it/rss/ambiente/rss2.0.xml",         "fonte": "Repubblica Ambiente", "categoria": "giornalismo"},
    {"url": "https://www.corriere.it/rss/ambiente.xml",                  "fonte": "Corriere Ambiente",   "categoria": "giornalismo"},
    {"url": "https://www.ilfattoquotidiano.it/category/ambiente/feed/",  "fonte": "IlFatto Ambiente",    "categoria": "giornalismo"},
    {"url": "https://www.nationalgeographic.it/feed",                    "fonte": "NatGeo Italia",       "categoria": "giornalismo"},
]

# === KEYWORD PER CATEGORIA TEMATICA ===
KEYWORDS = {
    "rischio_idrogeologico": [
        "alluvion", "esondazion", "frana", "frane", "franamento",
        "idrogeologic", "dissesto", "subsidenza", "inondazion",
        "rischio idraulic", "piano di bacino", "protezione civile",
        "emergenza meteo", "maltempo", "nubifragio", "acqua alta",
        "fiume", "torrente", "bacino", "reticolo idrico",
        "difesa del suolo", "assetto idraulic", "erosion",
        "geomorfolog", "rinaturalizzazion", "zone umide",
        "bollettino", "allerta", "vigilanza", "criticità", "criticita",
        "avviso meteo",
    ],
    "clima_estremo": [
        "cambiament. climatic", "climat", "siccit", "caldo estremo",
        "ondata di calore", "temperatura record", "precipitazioni intense",
        "evento estremo", "adattamento climatic", "resilienza",
        "emissioni", "co2", "decarbonizzazion",
        "ghiacciai", "innalzamento del mare", "sea level rise",
        "cop[0-9]", "ipcc", "riscaldamento global",
    ],
    "consumo_suolo": [
        "consumo di suolo", "impermeabilizzazion", "urbanizzazion",
        "cementificazion", "rigenerazione urban", "sprawl",
        "verde urban", "aree natural", "biodiversit",
        "monitoraggio ambient", "territorio",
    ],
}

# === PARAMETRI ===
MAX_AGE_HOURS  = 72      # ore — aumentato per catturare più notizie
MAX_ITEMS_OUTPUT = 5     # articoli mostrati sul sito
OUTPUT_JSON = "sottosuoli_news.json"
INDEX_HTML  = "index.html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def normalize_url(url: str) -> str:
    """Rimuove parametri UTM e query string per deduplicazione robusta."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")


def match_keywords(title: str, summary: str) -> list:
    """Restituisce le categorie tematiche che matchano il testo (regex)."""
    text = (title + " " + summary).lower()
    matched = []
    for categoria, patterns in KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, text):
                matched.append(categoria)
                break
    return matched


def parse_date(entry) -> datetime | None:
    """Estrae la data di pubblicazione dall'entry feedparser."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_feed(feed_config: dict) -> list:
    """Scarica e processa un singolo feed RSS con timeout e header espliciti."""
    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    try:
        # Usa requests per avere timeout e header controllati
        resp = requests.get(feed_config["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)

        if parsed.bozo and not parsed.entries:
            print(f"  ⚠️  {feed_config['fonte']}: feed malformato (bozo)")
            return items

        found = 0
        for entry in parsed.entries:
            title   = getattr(entry, "title", "").strip()
            summary = re.sub(r"<[^>]+>", "", getattr(entry, "summary", "")).strip()
            link    = getattr(entry, "link", "")
            pub     = parse_date(entry)

            # Salta articoli senza data (inaffidabili)
            if pub is None:
                continue

            # Salta se troppo vecchio
            if pub < cutoff:
                continue

            # Salta se nessuna keyword corrisponde
            categorie = match_keywords(title, summary)
            if not categorie:
                continue

            items.append({
                "titolo":    title,
                "sommario":  summary[:280],
                "link":      link,
                "fonte":     feed_config["fonte"],
                "categoria_fonte": feed_config["categoria"],
                "temi":      categorie,
                "data":      pub.strftime("%d %b %Y"),
                "data_iso":  pub.isoformat(),
            })
            found += 1

        print(f"  ✅ {feed_config['fonte']}: {found} articoli (su {len(parsed.entries)} totali)")

    except requests.exceptions.Timeout:
        print(f"  ⏱  {feed_config['fonte']}: timeout")
    except requests.exceptions.HTTPError as e:
        print(f"  ❌ {feed_config['fonte']}: HTTP {e.response.status_code}")
    except Exception as e:
        print(f"  ❌ {feed_config['fonte']}: {e}")

    return items


def tema_label(temi: list) -> str:
    labels = {
        "rischio_idrogeologico": "Rischio idrogeologico",
        "clima_estremo":         "Clima estremo",
        "consumo_suolo":         "Consumo di suolo",
    }
    return " · ".join(labels.get(t, t) for t in temi)


def update_html(items: list, html_path: str):
    """Aggiorna il blocco notizie in index.html tra i marker SOTTOSUOLI."""
    if not Path(html_path).exists():
        print(f"  ⚠️  {html_path} non trovato, salto aggiornamento HTML")
        return

    if not items:
        news_html = '      <div class="news-placeholder">Nessuna notizia nelle ultime 72 ore. Riprova domani.</div>'
    else:
        parts = []
        for item in items[:MAX_ITEMS_OUTPUT]:
            parts.append(
                f'      <a class="news-item" href="{item["link"]}" target="_blank" style="text-decoration:none;display:block;">\n'
                f'        <div class="news-tag">{tema_label(item["temi"])} · {escape(item["fonte"])}</div>\n'
                f'        <div class="news-title">{escape(item["titolo"])}</div>\n'
                f'        <div class="news-date">{item["data"]}</div>\n'
                f'      </a>'
            )
        news_html = "\n".join(parts)

    html = Path(html_path).read_text(encoding="utf-8")
    marker_start = "<!-- SOTTOSUOLI:START -->"
    marker_end   = "<!-- SOTTOSUOLI:END -->"
    new_block = f"{marker_start}\n{news_html}\n      {marker_end}"

    if marker_start in html:
        html = re.sub(
            rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}",
            new_block,
            html,
            flags=re.DOTALL,
        )
        print(f"  ✅ {html_path} aggiornato con {min(len(items), MAX_ITEMS_OUTPUT)} notizie")
    else:
        print(f"  ⚠️  Marker SOTTOSUOLI non trovato in {html_path}")

    Path(html_path).write_text(html, encoding="utf-8")


def main():
    print(f"\n🌍 Sottosuoli Collector v2 — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 52)

    all_items = []
    for feed in FEEDS:
        print(f"\n📡 {feed['fonte']} ({feed['categoria']})")
        all_items.extend(fetch_feed(feed))

    # Deduplicazione per URL normalizzato
    seen = set()
    unique = []
    for item in all_items:
        key = normalize_url(item["link"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Ordinamento per data decrescente (robusto)
    unique.sort(
        key=lambda x: datetime.fromisoformat(x["data_iso"])
        if x["data_iso"] else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    print(f"\n📊 Totale articoli unici trovati: {len(unique)}")

    # Salva JSON completo
    output = {
        "aggiornato": datetime.now(timezone.utc).isoformat(),
        "totale": len(unique),
        "articoli": unique,
    }
    Path(OUTPUT_JSON).write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"💾 Salvato {OUTPUT_JSON}")

    # Aggiorna HTML
    update_html(unique, INDEX_HTML)
    print("\n✅ Done.\n")


if __name__ == "__main__":
    main()
