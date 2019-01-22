import uuid
import datetime

import dateutil
import pytz


MESSAGE_BINDING = 'urn:taxii.mitre.org:message:xml:1.1'
SERVICES = 'urn:taxii.mitre.org:services:1.1'

PROTOCOLS = {
    'http': 'urn:taxii.mitre.org:protocol:http:1.0',
    'https': 'urn:taxii.mitre.org:protocol:https:1.0'
}

# 2014-12-19T00:00:00Z
TAXII_DT_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

EPOCH = datetime.datetime.utcfromtimestamp(0).replace(tzinfo=pytz.UTC)


def new_message_id():
    return str(uuid.uuid4())


def discovery_request(message_id=None):
    if message_id is None:
        message_id = new_message_id()

    return '''<Discovery_Request xmlns="http://taxii.mitre.org/messages/taxii_xml_binding-1.1" message_id="{}"/>'''.format(message_id)


def collection_information_request(message_id=None):
    if message_id is None:
        message_id = new_message_id()

    return '''<taxii_11:Collection_Information_Request xmlns:taxii_11="http://taxii.mitre.org/messages/taxii_xml_binding-1.1" message_id="{}"/>'''.format(message_id)


def poll_request(
        collection_name,
        exclusive_begin_timestamp,
        inclusive_end_timestamp,
        message_id=None,
        subscription_id=None):
    if message_id is None:
        message_id = new_message_id()

    exclusive_begin_timestamp = exclusive_begin_timestamp.strftime(TAXII_DT_FORMAT)
    inclusive_end_timestamp = inclusive_end_timestamp.strftime(TAXII_DT_FORMAT)

    result = [
        '<taxii_11:Poll_Request xmlns:taxii_11="http://taxii.mitre.org/messages/taxii_xml_binding-1.1"',
        'message_id="{}"'.format(message_id),
        'collection_name="{}"'.format(collection_name)
    ]
    if subscription_id is not None:
        result.append('subscription_id="{}"'.format(subscription_id))
    result.append('>')
    result.append('<taxii_11:Exclusive_Begin_Timestamp>{}</taxii_11:Exclusive_Begin_Timestamp>'.format(exclusive_begin_timestamp))
    result.append('<taxii_11:Inclusive_End_Timestamp>{}</taxii_11:Inclusive_End_Timestamp>'.format(inclusive_end_timestamp))

    if subscription_id is None:
        result.append('<taxii_11:Poll_Parameters allow_asynch="false"><taxii_11:Response_Type>FULL</taxii_11:Response_Type></taxii_11:Poll_Parameters>')

    result.append('</taxii_11:Poll_Request>')

    return '\n'.join(result)


def poll_fulfillment_request(result_id, result_part_number, collection_name, message_id=None):
    if message_id is None:
        message_id = new_message_id()

    return '''<taxii_11:Poll_Fulfillment xmlns:taxii_11="http://taxii.mitre.org/messages/taxii_xml_binding-1.1"
                message_id="{}" collection_name="{}" result_id="{}" result_part_number="{}"/>'''.format(message_id, collection_name, result_id, result_part_number)


def headers(content_type=None, accept=None, services=None, protocol=None):
    if content_type is None:
        content_type = MESSAGE_BINDING

    if accept is None:
        accept = MESSAGE_BINDING

    if services is None:
        services = SERVICES

    if protocol is None:
        protocol = 'urn:taxii.mitre.org:protocol:http:1.0'
    if protocol in PROTOCOLS:
        protocol = PROTOCOLS[protocol]

    return {
        'Content-Type': 'application/xml',
        'X-TAXII-Content-Type': content_type,
        'X-TAXII-Accept': accept,
        'X-TAXII-Services': services,
        'X-TAXII-Protocol': protocol
    }


def parse_timestamp_label(timestamp_label):
    try:
        dt = dateutil.parser.parse(timestamp_label)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        delta = dt - EPOCH
        return int(delta.total_seconds()*1000)

    except Exception:
        return None
