import asyncio
import time
from scraper import Scraper


async def main():
    num_pages = 100
    max_workers = 10

    print(f"Starting scraper with {max_workers} workers")
    start_time = time.time()

    scraper = Scraper(
        num_pages=num_pages,
        max_workers=max_workers,
        output_file="data/flats.csv"
    )

    await scraper.run()

    elapsed = round(time.time() - start_time, 2)
    print(f"\nDone! in {elapsed} seconds")



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled by user")