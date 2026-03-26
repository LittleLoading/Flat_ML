import os
import pandas as pd
import numpy as np
import math
from sklearn.neighbors import BallTree

# Absolutní cesty pro neprůstřelné spouštění
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FLATS = os.path.join(SCRIPT_DIR, '..', 'data', 'flats.csv')
INPUT_STOPS = os.path.join(SCRIPT_DIR, '..', 'data', 'mhd_stops.csv')
OUTPUT_PATH = os.path.join(SCRIPT_DIR, '..', 'data', 'flats_ml_ready.csv')


def prepare_for_ml(flats_csv=INPUT_FLATS, stops_csv=INPUT_STOPS, output_csv=OUTPUT_PATH):
    print("Načítám CSV soubory...")
    flats = pd.read_csv(flats_csv)
    stops = pd.read_csv(stops_csv)

    # Zastávky z OpenStreetMap (přejmenování hlavičky pro pořádek)
    stops = stops.rename(columns={'@lat': 'lat', '@lon': 'lon'})

    # Odstraníme řádky, kde chybí zásadní data
    flats = flats.dropna(subset=['price', 'area', 'lat', 'lon'])

    # --- GEOPROSTOROVÉ VÝPOČTY (MHD) ---
    print("Stavím prostorový strom (BallTree) pro hledání MHD...")
    stops_rad = np.deg2rad(stops[['lat', 'lon']].values)
    flats_rad = np.deg2rad(flats[['lat', 'lon']].values)

    tree = BallTree(stops_rad, metric='haversine')

    print("Hledám nejbližší zastávky pro všechny byty najednou...")
    distances_rad, indices = tree.query(flats_rad, k=1)

    # Převod na metry
    distances_meters = distances_rad.flatten() * 6371000
    flats['mhd_vzdalenost_metry'] = np.round(distances_meters)

    # --- PŘÍPRAVA ATRIBUTŮ PRO MODEL ---
    print("Zpracovávám textové atributy (Layout, Stav, Město)...")

    # 1. Dispozice
    flats['rooms'] = flats['layout'].str.extract(r'(\d+)').astype(float)
    flats['has_kk'] = flats['layout'].str.contains('kk', case=False, na=False).astype(int)

    # 2. Města (Top 15 + Ostatní) - MUSÍ BÝT PŘED ONE-HOT ENCODINGEM!
    top_15_cities = flats['city'].value_counts().nlargest(15).index
    flats['city_filtered'] = flats['city'].where(flats['city'].isin(top_15_cities), 'Ostatní')

    #Vyčištění zbytečností před One-Hot Encodingem
    cols_to_drop = ['layout', 'city', 'lat', 'lon']
    flats = flats.drop(columns=[col for col in cols_to_drop if col in flats.columns])

    # rozpad textu na one hot encoding
    flats = pd.get_dummies(flats, columns=['city_filtered', 'ownership', 'condition'], drop_first=False)

    # Převod True/False z One-Hot Encodingu na 1/0
    for col in flats.columns:
        if flats[col].dtype == bool:
            flats[col] = flats[col].astype(int)

    if 'url' in flats.columns:
        cols = [c for c in flats.columns if c != 'url'] + ['url']
        flats = flats[cols]

    flats.to_csv(output_csv, index=False)

    print(f"\n✅ HOTOVO! Výsledek byl uložen do souboru: {output_csv}")


if __name__ == "__main__":
    prepare_for_ml()