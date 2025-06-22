# GlucoWallet
Export in real time data from the Abbott Libre 2 GCM sensor.

Data is fetched using the credentials for the LibreLinkUp application. This app is
available under the "Connected apps" menu option in the LibreLink app.

On the main screen as show below tap the menu icon at the top right.
![LibreLink Overview](images/LibreLink%20Overview.png)

Tap on Connected apps near the bottom.
![Main Menu Expanded](images/Main%20Menu%20Expanded.png)

Click on LibreLinkUp to install and configure the app. LibreLinkUp is designed to be installed
on a second person's phone so they can also monitor the sensor being worn in case of
emergency.
![Connected apps Menu](images/Connected%20apps%20Menu.png)

# Setup
There are two options to set credentials for accessing both the sensor data and the database.

## Config File
```aiignore
cp glucowallet-config.ini.example ~/.config/glucowallet-config.ini
```

## Environment Variables
Export the following variables to provide access to LibreLinkUp and the optional
settings for the InfluxDB database.

### Credentials for LibreLinkUp
```
GLUCOWALLET_LINKUP_USERNAME=email@example.com
GLUCOWALLET_LINKUP_PASSWORD=secured-password
```

### Credentials for InfluxDB
```
GLUCOWALLET_INFLUXDB_URL=192.168.0.61:8086
GLUCOWALLET_INFLUXDB_BUCKET=glucowallet
GLUCOWALLET_INFLUXDB_ORG=Home
GLUCOWALLET_INFLUXDB_TOKEN=NRwJHbFhOzZkjp4dFg4XrqnQzBwGqNOYXztL8QNjfhaQXNoZ7z4Uh5sCyIRhyc42hpOj-lOGp5J1zgatXA0wbA==
```

# Thanks
[https://libreview-unofficial.stoplight.io/](https://libreview-unofficial.stoplight.io/) was the basis of this idea, the API docs here are great.
