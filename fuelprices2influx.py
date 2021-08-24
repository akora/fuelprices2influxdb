from influxdb import InfluxDBClient
from bs4 import BeautifulSoup
from datetime import datetime
import requests
import time
import os

# InfluxDB Settings
DB_ADDRESS = os.environ.get('DB_ADDRESS', '<IP addresss or localhost>')
DB_PORT = os.environ.get('DB_PORT', 8086)
DB_USER = os.environ.get('DB_USER', '<username>')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '<password>')
DB_DATABASE = os.environ.get('DB_DATABASE', '<database name>')
DB_RETRY_INVERVAL = int(os.environ.get('DB_RETRY_INVERVAL', 60)) # Time before retrying a failed data upload.

# Data Scraper Settings
TEST_INTERVAL = int(os.environ.get('TEST_INTERVAL', 3600))  # Time between tests (in seconds).
TEST_FAIL_INTERVAL = int(os.environ.get('TEST_FAIL_INTERVAL', 60))  # Time before retrying a failed scrape attempt (in seconds).

PRINT_DATA = os.environ.get('PRINT_DATA', "False") # Do you want to see the results in your logs? Type must be str. Will be converted to bool.

influxdb_client = InfluxDBClient(
    DB_ADDRESS, DB_PORT, DB_USER, DB_PASSWORD, None)

def str2bool(v):
  return v.lower() in ("yes", "true", "t", "1")

def logger(level, message):
    print(level, ":", datetime.now().strftime("%d/%m/%Y %H:%M:%S"), ":", message)

def init_db():
    try:
        databases = influxdb_client.get_list_database()
    except:
        logger("Error", "Unable to get list of databases")
        raise RuntimeError("No DB connection") from error
    else:
        if len(list(filter(lambda x: x['name'] == DB_DATABASE, databases))) == 0:
            influxdb_client.create_database(
                DB_DATABASE)  # Create if does not exist.
        else:
            influxdb_client.switch_database(DB_DATABASE)  # Switch to if does exist.


def get_fuel_prices():
    page = requests.get("https://holtankoljak.hu/index.php")
    soup = BeautifulSoup(page.content, 'html.parser')
    prices = soup.find_all(class_="price-rate")
    e10_95_min = prices[0]
    e10_95_min_value = (e10_95_min.find(class_="num").get_text())[:-5]
    e10_95_avg = prices[1]
    e10_95_avg_value = (e10_95_avg.find(class_="num").get_text())[:-5]
    e10_95_max = prices[2]
    e10_95_max_value = (e10_95_max.find(class_="num").get_text())[:-5]
    fuel_price_data = [
        {
            "measurement" : "fuel_prices",
            "tags" : {
                "data_source": "holtankoljak"
            },
            "fields" : {
                "e95_min": float(e10_95_min_value),
                "e95_avg": float(e10_95_avg_value),
                "e95_max": float(e10_95_max_value)
            }
        }
    ]
    return fuel_price_data

def main():
    db_initialized = False

    while(db_initialized == False):
        try:
            init_db()  # Setup the database if it does not already exist.
        except:
            logger("Error", "DB initialization error")
            time.sleep(int(DB_RETRY_INVERVAL))
        else:
            logger("Info", "DB initialization complete")
            db_initialized = True

    while (1):  # Run a scraping session and send the results to influxDB indefinitely.
        fuel_price_data = get_fuel_prices()
        logger("Info", "Data scraping successful")
        try:
            if influxdb_client.write_points(fuel_price_data) == True:
                logger("Info", "Data written to DB successfully")
                if str2bool(PRINT_DATA) == True:
                    logger("Info", fuel_price_data)
                time.sleep(TEST_INTERVAL)
        except:
            logger("Error", "Data write to DB failed")
            time.sleep(TEST_FAIL_INTERVAL)


if __name__ == '__main__':
    logger('Info', 'Fuel Prices Data Logger to InfluxDB started')
    main()
