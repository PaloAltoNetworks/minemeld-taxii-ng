import datetime

import pytz
import dateutil.parser

EPOCH = datetime.datetime.utcfromtimestamp(0).replace(tzinfo=pytz.UTC)


def parse_stix_timestamp(stix_timestamp):
    dt = dateutil.parser.parse(stix_timestamp)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    delta = dt - EPOCH
    return int(delta.total_seconds()*1000)
