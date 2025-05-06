import streamlit as st
import pandas as pd
import requests
import os

# 🧩 seitenkopf
st.title("🌿 SeedTogether Pflanzenberater")
st.write("Finde passende Pflanzen für deinen Balkon oder Garten basierend auf deinem Standort.")

# 📍 stadt eingabe
stadt = st.text_input("In welcher Stadt befindet sich dein Balkon oder Garten?")

# 🏡 standorttyp auswählen
standort_typ = st.radio("Wo möchtest du pflanzen?", ["Balkon", "Garten"])

# 🗂️ pflanzenliste laden mit pfadkontrolle
@st.cache_data
def lade_pflanzenliste():
    pfad = os.path.join(os.getcwd(), "pflanzen.csv")
    st.write("🔍 Gesuchter Pfad:", pfad)  # zeige den tatsächlichen Pfad an
    return pd.read_csv(pfad)

# lade csv
try:
    pflanzen_df = lade_pflanzenliste()
except FileNotFoundError:
    st.error("❌ Die Datei 'pflanzen.csv' wurde nicht gefunden. Bitte stelle sicher, dass sie im gleichen Ordner liegt wie app.py.")
    st.stop()

# 📤 testausgabe
if st.button("Zeige alle Pflanzen aus der Datenbank"):
    st.dataframe(pflanzen_df)

