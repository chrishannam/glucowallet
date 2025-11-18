#!/usr/bin/env python3
"""
InfluxDB Data Extractor
Extracts all raw data from an InfluxDB bucket without any aggregation or averaging.
"""

from configparser import ConfigParser

import pandas as pd
from influxdb_client import InfluxDBClient
from datetime import datetime
import os

from glucowallet.config import load_config

MEASUREMENT = "libreview_data"
FIELDS = ["glucose_level", "glucose_level_float"]


def extract_all_data(config):
    """Extract all raw data from the InfluxDB bucket."""

    # Initialize InfluxDB client
    client = InfluxDBClient(
        url=config["influxdb"]["url"],
        token=config["influxdb"]["token"],
        org=config["influxdb"]["org"],
    )
    query_api = client.query_api()

    # Flux query to get all raw data
    query = """
from(bucket: "gcm")
  |> range(start: -3w)
  |> filter(fn: (r) => r["_measurement"] == "libreview_data")
  |> filter(fn: (r) => r["_field"] == "glucose_level" or r["_field"] == "glucose_level_float")
  |> aggregateWindow(every: 1m, fn: last, createEmpty: false)
  |> yield(name: "1min_data")
    """

    print("Executing query to extract all data...")
    print(f"Query: {query}")

    try:
        # Execute query and convert to DataFrame
        result = query_api.query_data_frame(query)

        if result.empty:
            print("No data found in the bucket.")
            return None

        print(f"Retrieved {len(result)} data points")

        # Clean up the DataFrame
        if isinstance(result, list):
            # If multiple DataFrames returned, concatenate them
            result = pd.concat(result, ignore_index=True)

        # Select relevant columns
        columns_to_keep = ["_time", "_field", "_value"]

        # Add any tag columns that exist
        tag_columns = [
            col
            for col in result.columns
            if not col.startswith("_") and col not in ["result", "table"]
        ]
        columns_to_keep.extend(tag_columns)

        # Filter columns that actually exist in the result
        existing_columns = [col for col in columns_to_keep if col in result.columns]
        clean_result = result[existing_columns].copy()

        # Sort by time
        clean_result = clean_result.sort_values("_time")

        print(f"Data shape: {clean_result.shape}")
        print(
            f"Date range: {clean_result['_time'].min()} to {clean_result['_time'].max()}"
        )
        print(f"Fields found: {clean_result['_field'].unique()}")

        return clean_result

    except Exception as e:
        print(f"Error executing query: {e}")
        return None

    finally:
        client.close()


def save_to_csv(data, filename="influxdb_export.csv"):
    """Save DataFrame to CSV file."""
    try:
        data.to_csv(filename, index=False)
        print(f"Data saved to {filename}")
        print(f"File size: {os.path.getsize(filename) / (1024 * 1024):.2f} MB")
    except Exception as e:
        print(f"Error saving to CSV: {e}")


def save_to_json(data, filename="influxdb_export.json"):
    """Save DataFrame to JSON file."""
    try:
        # Convert datetime to string for JSON serialization
        data_copy = data.copy()
        data_copy["_time"] = data_copy["_time"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        data_copy.to_json(filename, orient="records", indent=2)
        print(f"Data saved to {filename}")
        print(f"File size: {os.path.getsize(filename) / (1024 * 1024):.2f} MB")
    except Exception as e:
        print(f"Error saving to JSON: {e}")


def print_data_summary(data):
    """Print a summary of the extracted data."""
    print("Summary")
    print("=" * 50)
    print(f"Total records: {len(data)}")
    print(f"Date range: {data['_time'].min()} to {data['_time'].max()}")
    print(f"Time span: {data['_time'].max() - data['_time'].min()}")
    print(f"Fields: {list(data['_field'].unique())}")

    # Value statistics by field
    for field in data["_field"].unique():
        field_data = data[data["_field"] == field]["_value"]
        print(f"\n{field} statistics:")
        print(f"  Count: {len(field_data)}")
        print(f"  Min: {field_data.min()}")
        print(f"  Max: {field_data.max()}")
        print(f"  Mean: {field_data.mean():.2f}")

    # Show first few records
    print("\nFirst 5 records:")
    print(data.head())

    print("\n" + "=" * 50)


def main(influxdb_config: ConfigParser):
    """Main function to extract from InfluxDB."""
    print("InfluxDB Data Extractor")
    print("=" * 30)

    # Extract data
    data = extract_all_data(config=influxdb_config)

    if data is None or data.empty:
        print("No data to export.")
        return

    # Print summary
    print_data_summary(data)

    # Save to files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"influxdb_export_{timestamp}.csv"
    json_filename = f"influxdb_export_{timestamp}.json"

    print("\nSaving data...")
    save_to_csv(data, csv_filename)
    save_to_json(data, json_filename)

    print("\nExport completed successfully!")
    print("Files created:")
    print(f"  - {csv_filename}")
    print(f"  - {json_filename}")


if __name__ == "__main__":
    config, filename = load_config()
    print(f"Config loaded from {filename}")
    print("Configuration check:")
    print(f"URL: {config['influxdb']['url']}")
    print(f"Bucket: {config['influxdb']['bucket']}")
    print(f"Measurement: {MEASUREMENT}")
    print(f"Fields: {FIELDS}")
    print()

    main(config)
