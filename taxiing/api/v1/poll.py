import uuid
import cStringIO
import json
from xml.sax.saxutils import escape
from datetime import datetime

from collections import defaultdict

from lxml import etree
from netaddr import AddrFormatError, IPRange

from flask import request, Response, stream_with_context
from flask.ext.login import current_user

from minemeld.flask.logger import LOG
from minemeld.flask.mmrpc import MMMaster
from minemeld.flask.redisclient import SR
from minemeld.flask import config

import taxiing.taxii.v11
import taxiing.stix.v2


FEED_INTERVAL = 100


def now_stix2_timestamp():
    # YYYY-MM-DDTHH:mm:ss.sssZ
    dtnow = datetime.utcnow()
    result = dtnow.strftime('%Y-%m-%dT%H:%M:%S')
    result = result+('.{:03d}Z'.format(int(dtnow.microsecond/1000)))
    return result


def get_ioc_property(feedname):
    if not config.get('FEEDS_AUTH_ENABLED', False):
        return None

    fattributes = config.get('FEEDS_ATTRS', None)
    if fattributes is None or feedname not in fattributes:
        return None

    return fattributes[feedname].get('ioc_tags_property', None)


def translate_ip_ranges(indicator):
    try:
        ip_range = IPRange(*indicator.split('-', 1))

    except (AddrFormatError, ValueError, TypeError):
        return [indicator]

    return [str(x) if x.size != 1 else str(x.network) for x in ip_range.cidrs()]


def stix2_bundle_formatter(feedname):
    authz_property = get_ioc_property(feedname)

    bundle_id = str(uuid.uuid3(
        uuid.NAMESPACE_URL,
        ('minemeld/{}/{}'.format(feedname, 0)).encode('ascii', 'ignore')
    ))

    last_entry = SR.zrange(feedname, -1, -1, withscores=True)
    if len(last_entry) != 0:
        _, score = last_entry[0]
        bundle_id = str(uuid.uuid3(
            uuid.NAMESPACE_URL,
            ('minemeld/{}/{}'.format(feedname, score)).encode('ascii', 'ignore')
        ))

    yield '{{\n"type": "bundle",\n"spec_version": "2.0",\n"id": "bundle--{}",\n"objects": [\n'.format(bundle_id)

    start = 0
    num = (1 << 32) - 1

    identities = defaultdict(uuid.uuid4)
    cstart = 0
    firstelement = True
    while cstart < (start + num):
        ilist = SR.zrange(
                    feedname, cstart,
                    cstart - 1 + min(start + num - cstart, FEED_INTERVAL)
                )

        result = cStringIO.StringIO()

        for indicator in ilist:
            v = SR.hget(feedname + '.value', indicator)

            if v is None:
                continue
            v = json.loads(v)

            if authz_property is not None:
                # authz_property is defined in config
                ioc_tags = v.get(authz_property, None)
                if ioc_tags is not None:
                    # authz_property is defined inside the ioc value
                    ioc_tags = set(ioc_tags)
                    if not current_user.can_access(ioc_tags):
                        # user has no access to this ioc
                        continue

            xindicators = [indicator]
            if '-' in indicator and v.get('type', None) in ['IPv4', 'IPv6']:
                xindicators = translate_ip_ranges(indicator)

            for i in xindicators:
                try:
                    converted = taxiing.stix.v2.encode(i, v)
                except RuntimeError:
                    LOG.error('Error converting {!r} to STIX2'.format(i))
                    continue

                created_by_ref = converted.pop('_created_by_ref', None)
                if created_by_ref is not None:
                    converted['created_by_ref'] = 'identity--'+str(identities[created_by_ref])

                if not firstelement:
                    result.write(',')
                firstelement = False

                result.write(json.dumps(converted))

        yield result.getvalue()

        result.close()

        if len(ilist) < 100:
            break

        cstart += 100

    # dump identities
    result = cStringIO.StringIO()
    for identity, uuid_ in identities.iteritems():
        identity_class, name = identity.split(':', 1)
        result.write(',')
        result.write(json.dumps({
            'type': 'identity',
            'id': 'identity--'+str(uuid_),
            'name': name,
            'identity_class': identity_class,
            'created': now_stix2_timestamp(),
            'modified': now_stix2_timestamp()
        }))
    yield result.getvalue()
    result.close()

    yield ']\n}'


def data_feed_11(rmsgid, cname):
    def _resp_generator():
        # yield the opening tag of the Poll Response
        yield taxiing.taxii.v11.poll_response_header(rmsgid, cname, 'urn:stix.mitre.org:json:2.0')

        for l in stix2_bundle_formatter(cname):
            yield escape(l)

        # yield the closing tag
        yield taxiing.taxii.v11.poll_response_footer()

    return Response(
        response=stream_with_context(_resp_generator()),
        status=200,
        headers={
            'X-TAXII-Content-Type': 'urn:taxii.mitre.org:message:xml:1.1',
            'X-TAXII-Protocol': 'urn:taxii.mitre.org:protocol:http:1.0'
        },
        mimetype='application/xml'
    )


def check_feed(cname):
    # check if feed exists
    status = MMMaster.status()
    tr = status.get('result', None)
    if tr is None:
        return False

    nname = 'mbus:slave:' + cname
    if nname not in tr:
        return False

    nclass = tr[nname].get('class', None)
    if nclass != 'minemeld.ft.redis.RedisSet':
        return False

    return True


def poll():
    taxiict = request.headers['X-TAXII-Content-Type']
    if taxiict == taxiing.taxii.v11.MESSAGE_BINDING:
        tm = etree.fromstring(request.data)
        if not tm.tag.endswith('Poll_Request'):
            return 'Invalid message', 400

        cname = tm.get('collection_name', None)
        message_id = tm.get('message_id', None)
        # taxii_version = '1.1'

    elif taxiict == 'urn:taxii.mitre.org:message:xml:1.0':
        return 'Not Supported', 400

        # tm = etree.fromstring(request.data)
        # if not tm.tag.endswith('Poll_Request'):
        #     return 'Invalid message', 400

        # cname = tm.get('feed_name', None)
        # message_id = tm.get('message_id', None)
        # taxii_version = '1.0'

    else:
        return 'Invalid message', 400

    if message_id is None or cname is None:
        return 'Invalid message', 400

    if not current_user.check_feed(cname):
        return 'Unauthorized', 401

    if not check_feed(cname):
        return 'Not Found', 404

    return data_feed_11(message_id, cname)
