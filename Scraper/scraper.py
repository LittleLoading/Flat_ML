import asyncio
import aiohttp
import csv
import re
import time


class Scraper:
    def __init__(self, num_pages=100, max_workers=10, output_file="flats.csv"):

        self.num_pages = num_pages
        self.max_workers = max_workers
        self.output_file = output_file

        self.queue = asyncio.Queue()
        self.csv_lock = asyncio.Lock()

        self.stats = {"saved": 0}


    def extract_layout(self,title):
        """
        Extract layout of flat as X+KK or X+Y from title
        :param title: 'Prodej bytu 3+kk 74 m²'
        :return: room layout as X+KK or X+Y
        """
        match = re.search(r'\d+\+(?:kk|\d+)', str(title))
        return match.group(0) if match else None


    def extract_area(self,title):
        """
        Extract layout of flat in m^2
        :param title: 'Prodej bytu 3+kk 74 m²'
        :return: flat space like 74m^2 -> returns int(74)
        """
        match = re.search(r'(\d+)\s*m²', str(title))
        return int(match.group(1)) if match else None


    def clean_city(self,locality_text):
        """
        To extract name of the city
        :param locality_text: locality text from api example: 'Šiklové, Praha 5 - Smíchov'
        :return: Name of the city like: str 'Praha 5'
        """
        loc = str(locality_text)

        CITIES = [
            "Praha 10", "Praha 1", "Praha 2", "Praha 3", "Praha 4",
            "Praha 5", "Praha 6", "Praha 7", "Praha 8", "Praha 9", "Praha",
            "České Budějovice", "Český Krumlov", "Jindřichův Hradec", "Písek",
            "Prachatice", "Strakonice", "Tábor",
            "Brno", "Blansko", "Břeclav", "Hodonín", "Vyškov", "Znojmo",
            "Karlovy Vary", "Cheb", "Sokolov",
            "Havlíčkův Brod", "Jihlava", "Pelhřimov", "Třebíč", "Žďár nad Sázavou",
            "Hradec Králové", "Rychnov nad Kněžnou", "Jičín", "Náchod", "Trutnov",
            "Jablonec nad Nisou", "Česká Lípa", "Liberec", "Semily",
            "Ostrava", "Frýdek-Místek", "Bruntál", "Karviná", "Nový Jičín", "Opava",
            "Olomouc", "Jeseník", "Prostějov", "Přerov", "Šumperk",
            "Ústí nad Orlicí", "Chrudim", "Pardubice", "Svitavy",
            "Plzeň", "Domažlice", "Klatovy", "Rokycany", "Tachov",
            "Mladá Boleslav", "Kutná Hora", "Benešov", "Beroun", "Kladno",
            "Kolín", "Mělník", "Nymburk", "Příbram", "Rakovník",
            "Ústí nad Labem", "Děčín", "Chomutov", "Litoměřice", "Louny",
            "Most", "Teplice",
            "Uherské Hradiště", "Kroměříž", "Vsetín", "Zlín"
        ]

        for city in CITIES:
            if city in loc:
                return city

        return "Ostatní"


    def has_outdoor_space(self,labels_all):
        """
        To check if flat has outdoor space
        :param labels_all: list of tags from Sreality API
        :return: 1 if there is outdoor space, 0 otherwise
        """
        all_labels = [item for sublist in labels_all for item in sublist]
        outdoor = {"balcony", "terrace", "loggia"}
        for label in all_labels:
            if label in outdoor:
                return 1
        return 0


    def find_value(self,items, *names):
        """
        Searches through list od dic and finds specific values
        :param items: a list of dictionaries containng specific name ar value pa
        :param names: characters that we search for inside items
        :return: the found value as string or None if not found
        """
        for item in items:
            if item.get("name") in names:
                val = item.get("value")
                if isinstance(val, list):
                    return " ".join(str(v) for v in val)
                return val
        return None


    async def fetch_listings_page(self,session, page_number):
        """
        Fetches singe page of flat listings from Sreality API
        :param session: active client session for making HTTP requests
        :param page_number: specific page number to retrive from search results
        :return: list of dictionaries, each dict is one flat list[dict]
        """
        url = "https://www.sreality.cz/api/cs/v2/estates"
        params = {
            "category_main_cb": 1,
            "category_type_cb": 1,
            "per_page": 100,
            "page": page_number
        }
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get("_embedded", {}).get("estates", [])


    async def fetch_flat_detail(self,session, estate_id):
        """
        Fetches full details of specific flat listing
        :param session: active client session for making HTTP requests
        :param estate_id: unique id of listing extracted from summary
        :return: dictionary with flat details
        """
        url = f"https://www.sreality.cz/api/cs/v2/estates/{estate_id}"
        async with session.get(url) as response:
            if response.status != 200:
                return None
            return await response.json()


    async def producer(self,queue, session):
        """
        Iterates through listing pages and adds the flats to queue
        :param queue: storage flat summaries for consumers
        :param session: active client session for making HTTP requests
        :return: None (just adds flats to queue)
        """
        for page_number in range(1, self.num_pages + 1):
            print(f"  [Producer] Fetching page {page_number}/{self.num_pages}...")
            flats = await self.fetch_listings_page(session, page_number)
            if not flats:
                break
            for flat in flats:
                await queue.put(flat)
            await asyncio.sleep(0.1)


    async def consumer(self,queue, session, writer, csv_lock, worker_id, stats):
        """
        Process flats from queue, fetches details and saves to csv
        :param queue: storage with flat summaries as dict
        :param session: active client session for making HTTP requests
        :param writer: CSV writer object
        :param csv_lock: asyncio.lock to prevent multiple consumers writing into file at same time
        :param worker_id: unique id of worker
        :param stats: a dict to track number of saved listings
        :return: None
        """
        while True:
            flat = await queue.get()

            try:
                estate_id = flat.get("_links", {}).get("self", {}).get("href", "").split("/")[-1]
                if not estate_id:
                    continue

                price = flat.get("price_czk", {}).get("value_raw")
                if not price or price <= 100000:
                    continue

                title = flat.get("name", "")
                raw_city = flat.get("locality", "")
                city = self.clean_city(raw_city)
                layout = self.extract_layout(title)
                area = self.extract_area(title)

                if not layout or not area:
                    continue

                gps = flat.get("gps", {})
                lat = gps.get("lat")
                lon = gps.get("lon")

                if not lat or not lon:
                    continue

                labels_all = flat.get("labelsAll", [[], []])
                outdoor = self.has_outdoor_space(labels_all)

                detail = await self.fetch_flat_detail(session, estate_id)
                if not detail:
                    continue

                items = detail.get("items", [])
                condition = self.find_value(items, "Stav objektu", "Stav", "Stav bytu")
                ownership = self.find_value(items, "Vlastnictví", "Vlastnictvi")

                if not condition or not ownership:
                    continue

                seo_locality = flat.get("seo", {}).get("locality", "unknown")
                url = f"https://www.sreality.cz/detail/prodej/byt/{layout}/{seo_locality}/{estate_id}"

                async with csv_lock:
                    writer.writerow([
                        price, city, layout, area,
                        condition, ownership, outdoor,
                        lat, lon, url
                    ])
                    stats["saved"] += 1
                    if stats["saved"] % 100 == 0:
                        print(f"  [Worker-{worker_id}] Saved {stats['saved']} flats so far...")

            except Exception as error:
                print(f"  [Worker-{worker_id}] Error: {error}")

            finally:
                queue.task_done()

    async def run(self):
        connector = aiohttp.TCPConnector(limit=15)  # maximal number of connections!
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            with open(self.output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["price", "city", "layout", "area", "condition", "ownership", "outdoor", "lat", "lon", "url"])


                producer_task = asyncio.create_task(self.producer(self.queue, session))
                consumer_tasks = []
                for i in range(self.max_workers):
                    worker_id = i + 1
                    task = asyncio.create_task(self.consumer(self.queue, session, writer, self.csv_lock, worker_id, self.stats))
                    consumer_tasks.append(task)
                await producer_task
                await self.queue.join()
                for task in consumer_tasks:
                    task.cancel()
            print(f"Done! Saved {self.stats['saved']} flats.")