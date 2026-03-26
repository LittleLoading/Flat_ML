#  ML Real Estate Price Predictor

This project is a comprehensive data and machine learning pipeline that automatically scrapes current flat listings from the real estate market (Sreality API), cleans the data, transforms it using geospatial calculations, and utilizes artificial intelligence to predict market prices.

---

## 1. Data Collection (Web Scraping)
Data is fetched from the public Sreality API using an asynchronous Python script (`aiohttp` and `asyncio`). The architecture utilizes a **Producer-Consumer** pattern with an async queue for maximum download speed and efficiency.

**Raw data extracted from the API (`flats.csv`):**
* `price` - Property price in CZK.
* `city` - Location / City.
* `layout` - Floor plan / layout (e.g., 3+kk, 2+1).
* `area` - Floor area in m².
* `condition` - Physical condition / Market status (New building, Before reconstruction, Reserved...).
* `ownership` - Type of ownership (Private, Cooperative...).
* `outdoor` - Binary flag (1/0) indicating if the flat has a balcony, loggia, or terrace.
* `lat` / `lon` - GPS coordinates of the flat.
* `url` - Link to the original listing.

---

##  2. Data Transformation (Feature Engineering)
Artificial intelligence cannot process raw text, so the data passes through the `prepare_data.py` script, which translates it into a clean mathematical matrix ready for ML models. 

**Applied transformations:**
1. **Geospatial Calculations (Public Transit):** Using a `BallTree` spatial index and the `haversine` metric, the distance to the nearest transit stop (from OpenStreetMap data in `mhd_stops.csv`) is calculated in meters for each flat.
2. **Feature Splitting:** The text-based layout is split into two numerical values:
   * `rooms` (int) - Number of rooms (e.g., extracted from "3+kk" -> 3).
   * `has_kk` (int 1/0) - Presence of a kitchenette (kk) vs. a separate kitchen.
3. **Frequency Filtering:** Only the top 15 most frequent cities are kept; the rest are aggregated into an "Other" category (preventing the curse of dimensionality).
4. **One-Hot Encoding:** Converting nominal text values (City, Ownership, Condition) into binary (True/False or 1/0) columns.
5. **Cleanup:** Removing original text columns and GPS coordinates. The `url` is kept at the end of the dataset strictly as meta-data for the frontend/visualization.

**Output:** A clean numerical matrix `flats_ml_ready.csv` containing approximately 30 features.

---

##  3. Machine Learning Models

* Random Forest Regressor -> price prediction
* Classification by price -> cheap, okay, overpriced 
* +url with similar flats