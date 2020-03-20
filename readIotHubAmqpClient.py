#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
from azure.eventhub.aio import EventHubConsumerClient
from influxdb import InfluxDBClient

import json
import logging
import time
from datetime import datetime

FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)

DB_NAME = os.getenv('INFLUXDB_DATABASE', 'mydb')

logging.info("Using database: '{0}'".format(DB_NAME))

influxdb_client = InfluxDBClient(os.getenv('INFLUXDB_HOSTNAME', 'influxdb'),
                                 os.getenv('INFLUXDB_PORT', '8086'),
                                 os.getenv('INFLUXDB_USER'),
                                 os.getenv('INFLUXDB_PASSWORD'),
                                 DB_NAME)


def connect_influxdb():
    while True:
        try:
            dbs = influxdb_client.get_list_database()
            if DB_NAME not in dbs:
                influxdb_client.create_database(DB_NAME)
        except Exception:
            logger.exception("Error connecting to InfluxDB. Retrying in 30sec")
            time.sleep(30)
            continue
        else:
            logging.info("connected to influxdb")
            break


def write_influxdb(payload):
    while True:
        try:
            influxdb_client.write_points(payload)
        except Exception:
            logger.exception("Error writing to InfluxDB. Retrying in 30sec")
            time.sleep(30)
            continue
        else:
            break


def convert_to_influx_format(message):
    name = message.annotations[b'iothub-connection-device-id']
    try:
        for jsonline in message.get_data():
            json_input = json.loads(jsonline)
    except json.decoder.JSONDecodeError:
        return

    if 'version' not in json_input:
        logging.warn('Ignoring event in unknown format')
        return

    if json_input["version"] != "0.0.1":
        logging.warn('Ignoring event wrong version')
        return

    time = datetime.fromtimestamp(int(json_input["time"]))
    data = json_input["fields"]

    temperature = float(data["TEMP"])
    humidity = float(data["HUMID"])
    air_pressure = float(data["AIR_PRESS"])

    json_body = [
        {'measurement': name, 'time': time, 'fields': {
            "temperature": temperature,
            "humidity": humidity,
            "air_pressure": air_pressure
        }}
    ]

    return json_body


async def on_event(partition_context, event):
    # Put your code here.
    # If the operation is i/o intensive, async will have better performance.
    #print("Received event from partition: {}.".format(partition_context.partition_id))
    logging.info("Event received: '{0}'".format(event.message))

    payload = convert_to_influx_format(event.message)

    if payload is not None:
        logging.info("Write points: {0}".format(payload))
        write_influxdb(payload)
    await partition_context.update_checkpoint(event)


async def on_partition_initialize(partition_context):
    # Put your code here.
    logging.info("Partition: {} has been initialized.".format(
        partition_context.partition_id))


async def on_partition_close(partition_context, reason):
    # Put your code here.
    logging.info("Partition: {} has been closed, reason for closing: {}.".format(
        partition_context.partition_id,
        reason
    ))


async def on_error(partition_context, error):
    # Put your code here. partition_context can be None in the on_error callback.
    if partition_context:
        logging.error("An exception: {} occurred during receiving from Partition: {}.".format(
            partition_context.partition_id,
            error
        ))
    else:
        logging.error(
            "An exception: {} occurred during the load balance process.".format(error))


async def main():
    connect_influxdb()

    client = EventHubConsumerClient.from_connection_string(
        conn_str=os.getenv('IOTHUB_CONNECTION_STRING'),
        consumer_group="$default",
        eventhub_name=os.getenv('IOTHUB_EVENTHUB_NAME')
    )

    async with client:
        await client.receive(
            on_event=on_event,
            on_error=on_error,
            on_partition_close=on_partition_close,
            on_partition_initialize=on_partition_initialize,
            # "-1" is from the beginning of the partition. @latest is only new
            starting_position="@latest",
        )

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
