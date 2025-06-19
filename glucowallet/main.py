import requests
import json
import csv
import os
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from glucowallet.config import load_config

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

    response = requests.post(login_url, json=payload, headers=HEADERS)

    if response.status_code == 200:
        return response.json()["data"]["authTicket"]["token"]
    else:
        raise ValueError(f"Authentication failed: {response.text}")


def fetch_account_data(token: str) -> dict:
    """Fetch user account data using the authentication token."""
    account_url = f"{HOST}/account"
    headers = HEADERS
    headers["Authorization"] = f"Bearer {token}"

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


def send_to_influxdb(sensor_reading, config):
    """Send LibreView data to InfluxDB."""
    client = InfluxDBClient(url=config["url"], token=config["token"], org=config["org"])
    write_api = client.write_api(write_options=SYNCHRONOUS)

    points = [
        (
            Point("libreview_data").field(
                "glucose_level_float",
                float(sensor_reading["glucoseMeasurement"]["Value"]),
            )
        ),
        (
            Point("libreview_data").field(
                "is_high", float(sensor_reading["glucoseItem"]["isHigh"])
            )
        ),
        (
            Point("libreview_data").field(
                "is_low", float(sensor_reading["glucoseItem"]["isLow"])
            )
        ),
        (
            Point("libreview_data").field(
                "trend_arrow", float(sensor_reading["glucoseItem"]["TrendArrow"])
            )
        ),
        (
            Point("libreview_data").field(
                "measurement_color",
                float(sensor_reading["glucoseItem"]["MeasurementColor"]),
            )
        ),
        (
            Point("libreview_data").field(
                "value_in_mg_per_pl",
                float(sensor_reading["glucoseItem"]["ValueInMgPerDl"]),
            )
        ),
    ]
    write_api.write(bucket=config["bucket"], org=config["org"], record=points)
    print("Data successfully written to InfluxDB.")

    client.close()


if __name__ == "__main__":
    config, filename = load_config()
    print(f"Config loaded from {filename}")

    try:
        token = authenticate(
            config["libre-linkup"]["username"], config["libre-linkup"]["password"]
        )
        print("Authentication successful.")

        account = fetch_account_data(token)
        reading = fetch_reading(token)

        latest_reading = reading["data"][0]

        print("Writing to InfluxDB...")
        send_to_influxdb(latest_reading, config["influxdb"])

        print("Latest Data:", json.dumps(reading["data"][0], indent=4))

    except Exception as e:
        raise e

    filename = "glucose_data.csv"
    file_exists = os.path.isfile(filename)

    with open(filename, mode="a", newline="") as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=latest_reading["glucoseMeasurement"].keys()
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(latest_reading["glucoseMeasurement"])
