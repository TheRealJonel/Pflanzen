# SeedTogether – Pflanzenberater
# Ziel: Nutzer:innen helfen, passende Pflanzen für Balkon oder Garten zu finden – basierend auf Standort, Lichtverh. u. Erf.
# Tools: Streamlit (Frontend), pandas (Datenverarbeitung), Open-Meteo APIs, HTML für Labels

import streamlit as st
import pandas as pd
import requests
import os
from streamlit_extras.metric_cards import style_metric_cards

# App-Konfiguration (Layout und Titel festlegen)
st.set_page_config(page_title="SeedTogether Pflanzenberater", layout="wide")

# Daten einlesen aus der lokalen CSV-Datei, "pflanzen_erweitert.csv"
@st.cache_data(show_spinner=False)
def lade_csv() -> pd.DataFrame:
    """
    Liest die CSV-Datei mit Pflanzendaten ein und bereinigt die Spaltennamen.

    Returns:
        pd.DataFrame: Tabelle mit Pflanzeninformationen
    """
    path = os.path.join(os.getcwd(), "pflanzen_erweitert.csv")
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower().str.replace("\\", "", regex=False)
    return df

# Geokoordinaten über Open-Meteo API abrufen um Standort zu bestimmen
@st.cache_data(ttl=3600)
def get_coords(city_name: str) -> dict[str, str | float] | None:
    """
    Ruft Koordinaten zu einer Stadt ab. Nutzt .get(), um API-Felder abzusichern.

    Args:
        city_name (str): Name der Stadt (z. B. "Berlin")

    Returns:
        dict[str, str | float] | None: Koordinaten und Ort, oder None bei Fehler
    """
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=de&format=json"
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()
        if "results" in data and data["results"]:
            r = data["results"][0]
            return {
                "lat": r.get("latitude"),
                "lon": r.get("longitude"),
                "stadt": r.get("name", ""),
                "land": r.get("country", "")
            }
    except (requests.RequestException, ValueError):
        return None

# Historische und aktuelle Wetterdaten abrufen
@st.cache_data(ttl=600)
def get_weather(lat: float, lon: float) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    """
    Ruft Wetterdaten (Temperatur, Sonnenstunden, Luftfeuchtigkeit, UV, AQI) ab.

    Args:
        lat (float): Breitengrad
        lon (float): Längengrad

    Returns:
        tuple: (Durchschnittstemperatur, Sonnenstunden, aktuelle Temperatur,
                Luftfeuchtigkeit, UV-Index, Luftqualitätsindex)
    """
    base = f"latitude={lat}&longitude={lon}"
    hist_url = f"https://archive-api.open-meteo.com/v1/archive?{base}&start_date=2019-01-01&end_date=2023-12-31&daily=temperature_2m_mean,sunshine_duration&timezone=Europe%2FBerlin"
    aktuell_url = f"https://api.open-meteo.com/v1/forecast?{base}&current=temperature_2m,relative_humidity_2m,uv_index&timezone=auto"
    air_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?{base}&current=european_aqi"

    hist = requests.get(hist_url, timeout=5).json() #was passiert
    aktuell = requests.get(aktuell_url, timeout=5).json()
    air = requests.get(air_url, timeout=5).json()

    temp = pd.Series(hist.get("daily", {}).get("temperature_2m_mean", [])).mean()
    sun = pd.Series(hist.get("daily", {}).get("sunshine_duration", [])).mean() / 3600

    return (
        round(temp, 1) if temp else None,
        round(sun, 1) if sun else None,
        aktuell["current"].get("temperature_2m"),
        aktuell["current"].get("relative_humidity_2m"),
        aktuell["current"].get("uv_index"),
        air.get("current", {}).get("european_aqi"),
    )

# HTML-Tag für visuelle Labels (z. B. "Anfänger", "Wenig Zeit")
def tag_html(text: str, color: str, icon: str = "") -> str:
    """
    Erstellt ein HTML-basiertes Label-Element.

    Args:
        text (str): Beschriftung
        color (str): Hintergrundfarbe
        icon (str, optional): Emoji-Icon

    Returns:
        str: HTML-Markup
    """
    return f"<span style='background-color:{color};color:white;padding:4px 10px;margin-right:6px;border-radius:12px;font-size:13px;'>{icon}{text}</span>"

# Anzeige von Wetterdaten im UI (als Metrik-Karten)
def zeige_metriken(temp: float | None, sun: float | None, temp_now: float | None, hum: float | None, uv: float | None, air: float | None) -> None:
    """
    Zeigt Wetterdaten als Metriken in vier Spalten.
    """
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📑 Ø Temp. (5 Jahre)", f"{temp} °C")
    c2.metric("☀ Sonnenstunden/Tag", f"{sun:.1f} h")
    c3.metric("🔥 Aktuelle Temp.", f"{temp_now} °C")
    c4.metric("💧 Luftfeuchtigkeit", f"{hum} %")
    style_metric_cards(background_color="#101010", border_left_color="#0099ff", border_color="#0099ff")
    st.markdown("🧪 **Luftqualität**")
    st.markdown(f"🌍 AQI (EU): {air if air is not None else '–'}  |  🌞 UV: {uv if uv is not None else '–'}")

# Darstellung einer Pflanze mit Bewertung und Infotext
def zeige_pflanze(row: pd.Series, diff_val: float | None = None, klima_temp: float | None = None) -> None:
    """
    Zeigt eine Pflanze mit Bewertung, Klimaverträglichkeit und Wikipedia-Zusatzinfos.
    """
    # Bewertungstext basierend auf der Temperaturabweichung
    if diff_val is not None:
        if diff_val <= 2:
            bewertung_html = tag_html("⭐ Sehr ähnlich", "#2ca02c")
        elif diff_val <= 4:
            bewertung_html = tag_html("⚠️ Okay", "#ff7f0e")
        else:
            bewertung_html = tag_html("🚫 Abweichend", "#d62728")
        # neu: verständliche Abweichungs-Beschreibung
        if klima_temp is not None:
            delta = round(diff_val, 1)
            if klima_temp < row["min_temp"]:
                diff_text = f"🔻 {abs(delta)} °C unter Idealtemperatur ({row['min_temp']} – {row['max_temp']} °C)"
            elif klima_temp > row["max_temp"]:
                diff_text = f"🔺 {delta} °C über Idealtemperatur ({row['min_temp']} – {row['max_temp']} °C)"
            else:
                diff_text = f"✅ Im Idealbereich ({row['min_temp']} – {row['max_temp']} °C)"
        else:
            diff_text = f"{diff_val} °C Abweichung"
        title = f"🌿 {row['name']} – {diff_text}"
    else:
        bewertung_html = ""
        title = f"🌾 {row['name']}"

    with st.expander(title, expanded=False):
        if bewertung_html:
            st.markdown(bewertung_html, unsafe_allow_html=True)

        if klima_temp is not None:
            # bereits durch diff_text abgedeckt, aber wir behalten separate Hinweise:
            if klima_temp < row["min_temp"]:
                st.error(f"🌡️ Achtung: Zu kalt ({klima_temp} °C < {row['min_temp']} °C)")
            elif klima_temp > row["max_temp"]:
                st.warning(f"☀️ Hinweis: Zu warm ({klima_temp} °C > {row['max_temp']} °C)")
            else:
                st.success(f"✅ Temperatur im Idealbereich ({row['min_temp']}–{row['max_temp']} °C)")

        st.markdown(f"**📝 Beschreibung:** {row['beschreibung']}")
        st.markdown(f"**🌸 Blütezeit:** {row['blütezeit']}")
        st.markdown(f"**📍 Standort:** {row['standort']}")
        st.markdown(f"**💡 Licht:** {row['licht']}")
        st.markdown(f"**🌱 Bodenart:** {row['bodenart']}")
        st.markdown(f"**🤝 Gute Nachbarn:** {row['begleitpflanzen']}")
        st.markdown(f"**📆 Monatstipps:** {row['monats_tipps']}")

        if row["max_temp"] < 30:
            st.warning("🔥 Keine starke Hitze verträglich.")
        if row["min_temp"] <= 5:
            st.success("❄️ Winterhart – kein Schutz nötig.")

        try:
            wiki = f"https://de.wikipedia.org/api/rest_v1/page/summary/{row['name']}"
            res = requests.get(wiki, timeout=5)
            if res.status_code == 200:
                d = res.json()
                st.markdown(f"**📖 {d.get('title', row['name'])} – Wikipedia:**\n\n{d.get('extract','')}")
                if thumb := d.get("thumbnail"):
                    st.image(thumb["source"], width=200)
        except requests.RequestException:
            pass

# UI – Header
st.markdown("""
<h1 style='color:white;'>🌱 SeedTogether Pflanzenberater</h1>
<p style='font-size:18px; color:white;'>
Finde passende Pflanzen für Balkon oder Garten basierend auf deinem Standort.
</p>
""", unsafe_allow_html=True)

# UI – Nutzereingaben
stadt = st.text_input("📍 Standort eingeben", placeholder="z. B. Berlin")
standort = st.radio("🏡 Standorttyp", ["Balkon", "Garten"], horizontal=True)
licht = st.selectbox("💡 Wie hell ist dein Standort?", ["sonnig", "halbschattig", "schattig"])
level = st.selectbox("👤 Dein Erfahrungslevel", ["Anfänger", "Fortgeschritten", "Experte"])
zeit = st.selectbox("⏱️ Wie viel Zeit willst du investieren?", ["Wenig", "Mittel", "Hoch"])

# Standortdaten abrufen
coords = None
if stadt:
    with st.spinner("🔍 Suche Standort und Wetter…"):
        coords = get_coords(stadt)
        if coords:
            temp, sun, temp_now, hum, uv, air = get_weather(coords["lat"], coords["lon"])
    if coords:
        st.success(f"📍 Gefunden: {coords['stadt']}, {coords['land']}")
        zeige_metriken(temp, sun, temp_now, hum, uv, air)
    else:
        st.warning("❗ Stadt nicht gefunden. Bitte korrigieren.")

# Pflanzen einlesen und filtern
try:
    pflanzen_df = lade_csv()
except FileNotFoundError:
    st.error("❌ Datei 'pflanzen_erweitert.csv' fehlt.")
    st.stop()

if coords and temp is not None:
    perfect = pflanzen_df[
        (pflanzen_df["min_temp"] <= temp) &
        (pflanzen_df["max_temp"] >= temp) &
        (pflanzen_df["standort"].str.lower().isin([standort.lower(), "beides"])) &
        (pflanzen_df["licht"].str.lower() == licht.lower()) &
        (pflanzen_df["level"].str.lower() == level.lower()) &
        (pflanzen_df["zeitaufwand"].str.lower() == zeit.lower())
    ]

    candidates = pflanzen_df[
        (pflanzen_df["min_temp"] <= temp * 1.1) &
        (pflanzen_df["max_temp"] >= temp * 0.9) &
        (pflanzen_df["standort"].str.lower().isin([standort.lower(), "beides"]))
    ].copy()
    candidates["temp_mid"] = (candidates["min_temp"] + candidates["max_temp"]) / 2
    candidates["diff"] = (candidates["temp_mid"] - temp).abs()
    similar = candidates[~candidates["name"].isin(perfect["name"])].nsmallest(3, "diff")

    st.markdown("## 🌿 Empfohlene Pflanzen")
    st.markdown(
        tag_html(level, "#1f77b4", "🧠 ") +
        tag_html(zeit, "#ff7f0e", "🕓 ") +
        tag_html("Wasser", "#2ca02c", "💧 "),
        unsafe_allow_html=True,
    )

    if perfect.empty:
        st.info("🚫 Keine perfekte Übereinstimmung gefunden.")
    else:
        st.markdown("### 🔥 Perfekte Treffer")
        for _, row in perfect.iterrows():
            zeige_pflanze(row, klima_temp=temp)

    if not similar.empty:
        st.markdown("### 🌱 Nahe Alternativen")
        st.info(
            "Diese Pflanzen passen nicht exakt zu deinem Standort und deinen Anforderungen, sind aber vom Zeitaufwand und Bedingungen ähnlich. "
            "Mit einfachen Anpassungen – wie einem geschützten Standort, zusätzlichem Gießen bei Hitze "
            "oder Winterschutz – können sie trotzdem gut gedeihen."
        )
        for _, row in similar.iterrows():
            zeige_pflanze(row, round(row["diff"], 1), klima_temp=temp)


    if perfect.empty and similar.empty:
        st.markdown("### 🎲 Zufällige Vorschläge")
        st.info(
            "Hier sind zufällig ausgewählte Pflanzen, die nicht exakt zu deinem Standort passen. "
            "Sie können als Inspiration dienen – prüfe die Details und entscheide, "
            "ob du sie mit etwas Aufwand dennoch kultivieren möchtest."
        )
        for _, row in pflanzen_df.sample(5, random_state=1).iterrows():
            zeige_pflanze(row, klima_temp=temp)
