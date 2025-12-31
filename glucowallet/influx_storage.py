def create_influx_point(sensor_reading: dict, point_class):
    """
    Create an InfluxDB Point from sensor reading data.
    """
    return (
        point_class("libreview_data")
        .tag("patientId", sensor_reading["patientId"])
        .tag("sensor_serial_number", sensor_reading["sensor"]["sn"])
    )
