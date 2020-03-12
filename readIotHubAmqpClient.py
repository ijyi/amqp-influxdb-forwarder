#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
from azure.eventhub.aio import EventHubConsumerClient
from influxdb import InfluxDBClient

import configparser
import json
import logging
import time

# Config file must be bound to docker image at runtime
CONFIG_FILE_PATH = 'config/config.properties'

FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger(__name__)

configp = configparser.ConfigParser()
configp.read(CONFIG_FILE_PATH)

influx_config = configp['influxdb']
DB_NAME = influx_config['DATABASE']
logging.info("Using database: '{0}'".format(DB_NAME))

influxdb_client = InfluxDBClient(influx_config['HOSTNAME'],
                                 influx_config['PORT'],
                                 influx_config['USER'],
                                 influx_config['PASSWORD'],
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

    if 'temperature_C' not in json_input or 'humidity' not in json_input or 'battery' not in json_input:
        logging.warn('Ignoring event in unknown format')
        return

    time = json_input["time"]
    temperature = json_input["temperature_C"]
    humidity = json_input["humidity"]
    battery_status = json_input["battery"]

    json_body = [
        {'measurement': name, 'time': time, 'fields': {
            "temperature": temperature,
            "humidity": humidity,
            "battery": battery_status
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
    azure_config = configp['azure']
    client = EventHubConsumerClient.from_connection_string(
        conn_str=azure_config['CONNECTION_STR'],
        consumer_group="$default",
        eventhub_name=azure_config['EVENTHUB_NAME']
    )

    connect_influxdb()

    async with client:
        await client.receive(
            on_event=on_event,
            on_error=on_error,
            on_partition_close=on_partition_close,
            on_partition_initialize=on_partition_initialize,
            # "-1" is from the beginning of the partition. @latest is only new
            starting_position="-1",
        )

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
