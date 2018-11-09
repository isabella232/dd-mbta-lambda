# -*- coding: utf-8 -*-
import os

import requests
from datadog import api, initialize, ThreadStats
from google.transit import gtfs_realtime_pb2
from stops import stop_names
from routes import route_names

options = {
    'api_key': os.environ.get('DD_API_KEY'),
    'app_key': os.environ.get('DD_APP_KEY')
}

initialize(**options)


def handler(event, context):
    stats = ThreadStats()
    stats.start()

    trip_feed = gtfs_realtime_pb2.FeedMessage()
    trip_response = requests.get('https://cdn.mbta.com/realtime/TripUpdates.pb')
    trip_feed.ParseFromString(trip_response.content)
    trip_feed_ts = trip_feed.header.timestamp
    counter = 0
    for entity in trip_feed.entity:
        if entity.HasField('trip_update'):
            trip_update = entity.trip_update
            route_name = trip_update.trip.route_id
            if trip_update.trip.route_id in route_names:
                route_name = route_names[trip_update.trip.route_id]
            last_stop_id = trip_update.stop_time_update[len(trip_update.stop_time_update) - 1].stop_id
            destination = stop_names[last_stop_id]
            trip_id = trip_update.trip.trip_id
            vehicle = trip_update.vehicle.label

            for stop in trip_update.stop_time_update:
                counter += 1
                stop_name = stop_names[stop.stop_id]

                if stop.departure.time > 0:
                    if stop.arrival.time > 0:
                        # mid-route stop, use arrival time
                        time = stop.arrival.time
                    else:
                        # first stop, use departure time
                        time = stop.departure.time
                else:
                    # last stop, ignore
                    continue

                arrives_in = (time - trip_feed_ts)
                tags = [
                    'trip_id:{}'.format(trip_id),
                    'stop:{}'.format(stop_name),
                    'destination:{}'.format(destination),
                    'vehicle:{}'.format(vehicle),
                    'route:{}'.format(route_name),
                ]
                stats.gauge('mbta.trip.arrival_secs', arrives_in, tags=tags)
                stats.gauge('mbta.trip.arrival_min', arrives_in / 60, tags=tags)
                if counter % 100 == 0:
                    stats.flush()

    saFeed = gtfs_realtime_pb2.FeedMessage()
    saResponse = requests.get('https://cdn.mbta.com/realtime/Alerts.pb')
    saFeed.ParseFromString(saResponse.content)
    for entity in saFeed.entity:
        if entity.HasField('alert'):
            include_alert = False
            for informed in entity.alert.informed_entity:
                if informed.route_type == 1:  # Subway
                    include_alert = True
                    break
            if include_alert:
                print(entity.alert)

    stats.flush()
