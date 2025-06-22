from configparser import SectionProxy

import requests
import csv
import os
import logging
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from glucowallet.config import load_config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


HOST = "https://api.libreview.io"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "product": "llu.android",
    "version": "4.7",
}


def authenticate(email: str, password: str) -> str:
    """Authenticate with LibreView API and return the Bearer token."""
    login_url = f"{HOST}/llu/auth/login"
    payload = {"email": email, "password": password}

    try:
        response = requests.post(login_url, json=payload, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()["data"]["authTicket"]["token"]
    except requests.RequestException as e:
        logging.error(f"Authentication request failed: {e}")
        raise
    except KeyError:
        logging.error("Authentication response structure unexpected.")
        raise


def fetch_account_data(bearer_token: str) -> dict:
    """Fetch user account data using the authentication token."""
    account_url = f"{HOST}/account"
    headers = HEADERS
    headers["Authorization"] = f"Bearer {bearer_token}"

    response = requests.get(account_url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        raise ValueError(f"Failed to fetch account data: {response.text}")


def accept_terms(token: str) -> dict:
    """Fetch user account data using the authentication token."""
    account_url = f"{HOST}/auth/continue/tou"
    headers = HEADERS
    headers["Authorization"] = f"Bearer {token}"

    response = requests.post(account_url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        raise ValueError(f"Failed to fetch account data: {response.text}")


def fetch_reading(token: str) -> dict:
    account_url = f"{HOST}/llu/connections"
    headers = HEADERS
    headers["Authorization"] = f"Bearer {token}"

    response = requests.get(account_url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        raise ValueError(f"Failed to fetch account data: {response.text}")


def base_point(sensor_reading):
    """Save pasting the same .tag"""
    return (
        Point("libreview_data")
        .tag("patientId", sensor_reading["patientId"])
        .tag("sensor_serial_number", sensor_reading["sensor"]["sn"])
    )


def send_to_influxdb(sensor_reading: dict, influxdb_config: SectionProxy) -> None:
    """Send LibreView data to InfluxDB."""
    client = InfluxDBClient(
        url=influxdb_config["url"],
        token=influxdb_config["token"],
        org=influxdb_config["org"],
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    points = [
        base_point(sensor_reading).field(
            "glucose_measurement", float(sensor_reading["glucoseMeasurement"]["Value"])
        ),
        base_point(sensor_reading).field(
            "is_high", float(sensor_reading["glucoseItem"]["isHigh"])
        ),
        base_point(sensor_reading).field(
            "is_low", float(sensor_reading["glucoseItem"]["isLow"])
        ),
        base_point(sensor_reading).field(
            "trend_arrow", float(sensor_reading["glucoseItem"]["TrendArrow"])
        ),
        base_point(sensor_reading).field(
            "measurement_color",
            float(sensor_reading["glucoseItem"]["MeasurementColor"]),
        ),
        base_point(sensor_reading).field(
            "value_in_mg_per_pl", float(sensor_reading["glucoseItem"]["ValueInMgPerDl"])
        ),
    ]

    write_api.write(
        bucket=influxdb_config["bucket"], org=influxdb_config["org"], record=points
    )
    print("Data successfully written to InfluxDB.")

    client.close()


def write_to_csv(reading_to_update):
    """Write LibreView data to CSV. Create the file if it doesn't exist, next time append to the file."""

    csv_file = "glucose_data.csv"
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, mode="a", newline="") as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=reading_to_update["glucoseMeasurement"].keys()
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(reading_to_update["glucoseMeasurement"])

    logging.info(f"Data appended to {csv_file}")


if __name__ == "__main__":
    config, filename = load_config()
    print(f"Config loaded from {filename}")

    token = authenticate(
        config["libre-linkup"]["username"], config["libre-linkup"]["password"]
    )
    print("Authentication successful.")

    account = fetch_account_data(token)
    reading = fetch_reading(token)

    latest_reading = reading["data"][0]

    if "influxdb" in config:
        print("Writing to InfluxDB...")
        send_to_influxdb(latest_reading, config["influxdb"])

    write_to_csv(latest_reading)
    print("Done.")
