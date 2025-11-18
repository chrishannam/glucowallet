"""
Runner file for collecting and sending data.
"""

from configparser import SectionProxy
import csv
import logging
import os
import hashlib

import requests

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from glucowallet.config import load_config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


HOST = "https://api.libreview.io"

HEADERS = {
    "accept-encoding": "gzip",
    "Content-Type": "application/json",
    "Accept": "application/json, application/xml, multipart/form-data",
    "product": "llu.ios",
    "version": "4.16.0",
    "User-Agent": "LibreLink/4.16.0 (iPhone; iOS 17.0; Scale/3.00)",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}


def _get_url(
    url: str,
    method: str = "GET",
    auth_token: str = "",
    json_payload=None,
    headers=None,
) -> dict:
    """Make a request and return the response JSON, handling errors."""
    merged_headers = headers.copy() if headers else HEADERS.copy()
    if auth_token:
        merged_headers["Authorization"] = f"Bearer {auth_token}"

    try:
        if method.upper() == "POST":
            response = requests.post(
                url, json=json_payload, headers=merged_headers, timeout=10
            )
        elif method.upper() == "GET":
            response = requests.get(url, headers=merged_headers, timeout=10)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error("HTTP request failed: %s", e)
        raise ValueError(f"Failed to fetch data from {url}: {str(e)}") from e
    except ValueError as e:
        logging.error(
            "Response content is not valid JSON or had an unexpected value: %s", e
        )
        raise
    except KeyError as e:
        logging.error("Expected key missing in response: %s", e)
        raise


def authenticate(email: str, password: str):
    """Authenticate with LibreView API and return the Bearer token."""

    response = _get_url(
        url=f"{HOST}/llu/auth/login",
        method="POST",
        json_payload={"email": email, "password": password},
    )

    try:
        return response["data"]["authTicket"]["token"], response["data"]["user"]["id"]
    except KeyError:
        logging.error("Authentication response structure unexpected: %s", response)
        raise


def get_connections(auth_token):
    """Get available connections for our creds."""
    return _get_url(url=f"{HOST}/llu/connections", method="GET", auth_token=auth_token)


def fetch_graph(auth_token, patient_id):
    """Fetch graph data for user."""
    return _get_url(
        url=f"{HOST}/llu/connections/{patient_id}/graph",
        method="GET",
        auth_token=auth_token,
    )


def fetch_logbook(auth_token, patient_id):
    """Fetch logbook data for user from the endpoint:
    https://api.libreview.io/llu/connections/{patientId}/logbook
    """
    return _get_url(
        url=f"{HOST}/llu/connections/{patient_id}/logbook",
        method="GET",
        auth_token=auth_token,
    )


def fetch_account_data(bearer_token: str) -> dict:
    """Fetch user account data using the authentication token."""
    account_url = f"{HOST}/account"
    return _get_url(url=account_url, method="GET", auth_token=bearer_token)


def accept_terms(terms_token: str) -> dict:
    """Accept terms of use with token."""
    return _get_url(
        url=f"{HOST}/auth/continue/tou", method="POST", auth_token=terms_token
    )


def fetch_reading(auth_token: str, account_id: str) -> dict:
    """Fetch user reading using the authentication token."""
    account_url = f"{HOST}/llu/connections"
    headers = HEADERS
    headers["authorization"] = f"Bearer {auth_token}"
    # thanks to https://github.com/TA2k/ioBroker.libre/commit/e29c214919ae493d8b2ef92ae395e98435b03179
    headers["account-id"] = hashlib.sha256(account_id.encode()).hexdigest()

    response = requests.get(account_url, headers=headers, timeout=10)

    if response.status_code == 200:
        return response.json()

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

    alarm_rules = sensor_reading.get("alarmRules", {})
    glucose_measurement = sensor_reading.get("glucoseMeasurement", {})
    glucose_item = sensor_reading.get("glucoseItem", {})

    # Define fields with cleaner paths
    fields = {
        "low_alarm_thmm": float(alarm_rules.get("l", {}).get("thmm", 0)),
        "high_alarm_thmm": float(alarm_rules.get("h", {}).get("thmm", 0)),
        "value_in_mg_per_dl": float(glucose_measurement.get("ValueInMgPerDl", 0)),
        "glucose_trend_arrow": float(glucose_measurement.get("TrendArrow", 0)),
        "glucose_measurement": float(glucose_measurement.get("Value", 0)),
        "is_high": float(glucose_item.get("isHigh", False)),
        "is_low": float(glucose_item.get("isLow", False)),
        "item_trend_arrow": float(glucose_item.get("TrendArrow", 0)),
        "measurement_color": float(glucose_item.get("MeasurementColor", 0)),
        "value_in_mg_per_pl": float(glucose_item.get("ValueInMgPerDl", 0)),
        "glucose_units": float(glucose_item.get("GlucoseUnits", 0)),
        "glucose_item_value": float(glucose_item.get("Value", 0)),
        "glucose_item_type": float(glucose_item.get("type", 0)),
    }

    points = [
        base_point(sensor_reading).field(field_name, value)
        for field_name, value in fields.items()
    ]

    write_api.write(
        bucket=influxdb_config["bucket"], org=influxdb_config["org"], record=points
    )
    print("Data successfully written to InfluxDB.")

    client.close()


def write_to_csv(reading_to_update):
    """Write LibreView data to CSV. Create the file if it doesn't exist,
    next time append to the file."""

    csv_file = "glucose_data.csv"
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=reading_to_update["glucoseMeasurement"].keys()
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(reading_to_update["glucoseMeasurement"])

    logging.info("Data appended to %s", csv_file)


if __name__ == "__main__":
    config, filename = load_config()
    print(f"Config loaded from {filename}")

    token, account_id = authenticate(
        config["libre-linkup"]["username"], config["libre-linkup"]["password"]
    )
    print("Authentication successful.")

    # connections = get_connections(token)
    # accept_terms(token)
    reading = fetch_reading(token, account_id)
    latest_reading = reading["data"][0]
    patient_id = latest_reading["patientId"]

    # graph_data = fetch_graph(token, patient_id)

    if "influxdb" in config:
        print("Writing to InfluxDB...")
        send_to_influxdb(latest_reading, config["influxdb"])

    write_to_csv(latest_reading)
    print("Done.")
