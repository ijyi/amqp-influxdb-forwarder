# amqp-influxdb-forwarder
Small utility to read messages from Azure IoThub and forward to InfluxDB.

### Flow:
1) Receive events from Azure IotHub using AMQP
2) Convert from IotHub format to InfluxDB JSON format and ensure (custom) properties are in payload
3) Write new message to influxdb

In case of (network) errors: 
1. sleep for 30 seconds
2. retry
3. still an error? goto 1


If restarted it will read all messages from the beginning of the queue. InfluxDB will ignore duplicate entries.


Packaged with Docker. Image available here: https://hub.docker.com/r/ijyi/amqp-influxdb-forwarder/


### Build
<pre>
docker build -t ijyi/amqp-influxdb-forwarder:latest . 
</pre>

### Test run
<pre>
docker run -d --name influxdb -p 8083:8083 -p 8086:8086 influxdb
docker run --net container:influxdb  -v $(pwd)/config.properties:/config.properties ijyi/amqp-influxdb-forwarder 
</pre>


### Local OSX test AMQP client
<pre>
brew install openssl
export LDFLAGS="-L/usr/local/opt/openssl/lib"
export CPPFLAGS="-I/usr/local/opt/openssl/include"
export PKG_CONFIG_PATH="/usr/local/opt/openssl/lib/pkgconfig"

pip3 install python-qpid-proton
</pre>

### Configuration
Configuration is supplied via environment variables
| Environment Variable     | Description                         | Default  |
| ------------------------ | ----------------------------------- | -------- |
| INFLUXDB_HOSTNAME        | InfluxDB Hostname                   | influxdb |
| INFLUXDB_PORT            | InfluxDB Port                       | 8086     |
| INFLUXDB_USER            | InfluxDB Username                   | None     |
| INFLUXDB_PASSWORD        | InfluxDB Password                   | None     |
| INFLUXDB_DATABASE        | InfluxDB Database Name              | mydb     |
| IOTHUB_CONNECTION_STRING | IoT Hub Event Hub connection string | None     |
| IOTHUB_EVENTHUB_NAME     | IoT Hub Event Name                  | None     |

### Azure and AMQP
Info about amqp settings: https://github.com/Azure/azure-sdk-for-python/tree/eventhub_track1/sdk/eventhub/azure-eventhubs


### Docker housekeeping

Remove dangling images
<pre>
docker rmi $(docker images -f "dangling=true" -q)
</pre>

Attach to running container
<pre>
docker exec -i -t influxdb /bin/bash 
</pre>
