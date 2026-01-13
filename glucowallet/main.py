"""
Runner file for collecting and sending data.
"""

import csv
import logging
import os

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from pylibrelinkup.models.data import GlucoseMeasurementWithTrend

from glucowallet.config import load_config
from pylibrelinkup import PyLibreLinkUp

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def send_to_influxdb(
    sensor_reading: GlucoseMeasurementWithTrend, influxdb_config: dict
) -> None:
    """Send LibreView data to InfluxDB."""

    # Validate required fields
    required_fields = ["url", "token", "org", "bucket"]
    missing_fields = [
        field for field in required_fields if field not in influxdb_config
    ]

    if missing_fields:
        raise ValueError(
            f"Missing required InfluxDB configuration fields: {', '.join(missing_fields)}"
        )

    client = InfluxDBClient(
        url=influxdb_config["url"],
        token=influxdb_config["token"],
        org=influxdb_config["org"],
    )

    write_api = client.write_api(write_options=SYNCHRONOUS)

    # Define fields with cleaner paths
    fields = {
        "measurement_color": float(sensor_reading.measurement_color),
        "glucose_measurement": float(sensor_reading.value),
        "is_high": float(sensor_reading.is_high),
        "is_low": float(sensor_reading.is_low),
        "trend": float(sensor_reading.trend.value),
        "value_in_mg_per_pl": float(sensor_reading.value_in_mg_per_dl),
        "glucose_units": float(sensor_reading.glucose_units),
    }

    points = [
        Point("freestyle_librelink").field(field_name, value)
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

    libre_client = PyLibreLinkUp(
        email=config["libre-linkup"]["username"],
        password=config["libre-linkup"]["password"],
    )
    libre_client.authenticate()
    print("Authentication successful.")

    patient_list = libre_client.get_patients()
    latest_glucose = libre_client.latest(patient_identifier=patient_list[0])

    if "influxdb" in config:
        print("Writing to InfluxDB...")
        send_to_influxdb(latest_glucose, config["influxdb"])

    # write_to_csv(latest_glucose)
    print("Done.")
