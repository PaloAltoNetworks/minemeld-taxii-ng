#  Copyright 2019 Palo Alto Networks, Inc
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import uuid
import cStringIO
from collections import defaultdict
import json

from flask import stream_with_context, Response
from flask_login import current_user
from netaddr import IPRange, AddrFormatError

from minemeld.flask.redisclient import SR
from minemeld.flask.logger import LOG

import taxiing.stix.v2 as stix2

from .utils import get_ioc_property


FEED_INTERVAL = 100


def translate_ip_ranges(indicator):
    try:
        ip_range = IPRange(*indicator.split('-', 1))

    except (AddrFormatError, ValueError, TypeError):
        return [indicator]

    return [str(x) if x.size != 1 else str(x.network) for x in ip_range.cidrs()]


def response_formatter(feedname, objectid='', manifest=False):
    authz_property = get_ioc_property(feedname)

    if not manifest:
        bundle_id = str(uuid.uuid3(
            uuid.NAMESPACE_URL,
            ('minemeld/{}/{}'.format(feedname, 0)).encode('ascii', 'ignore')
        ))

        last_entry = SR.zrange(feedname, -1, -1, withscores=True)
        LOG.debug(last_entry)
        if len(last_entry) != 0:
            _, score = last_entry[0]
            bundle_id = str(uuid.uuid3(
                uuid.NAMESPACE_URL,
                ('minemeld/{}/{}'.format(feedname, score)).encode('ascii', 'ignore')
            ))

        yield '{{\n"type": "bundle",\n"spec_version": "2.0",\n"id": "bundle--{}",\n"objects": [\n'.format(bundle_id)

    else:
        yield '{\n"objects": [\n'

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
                    converted = stix2.encode(i, v)
                except RuntimeError:
                    LOG.error('Error converting {!r} to STIX2'.format(i))
                    continue

                if not manifest:
                    if objectid and converted['id'] != objectid:
                        # skip indicators that don't match the provided id
                        continue

                    created_by_ref = converted.pop('_created_by_ref', None)
                    if created_by_ref is not None:
                        converted['created_by_ref'] = 'identity--'+str(identities[created_by_ref])
                else:
                    converted = dict(id=converted['id'])

                if not firstelement:
                    result.write(',')
                firstelement = False

                result.write(json.dumps(converted))

        yield result.getvalue()

        result.close()

        if len(ilist) < 100:
            break

        cstart += 100

    if not manifest:
        # dump identities
        result = cStringIO.StringIO()
        for identity, uuid_ in identities.iteritems():
            identity_class, name = identity.split(':', 1)
            result.write(',')
            result.write(json.dumps({
                'type': 'identty',
                'id': 'identity--'+str(uuid_),
                'name': name,
                'identity_class': identity_class
            }))
        yield result.getvalue()
        result.close()

    yield ']\n}'


def generate_taxii2_collection(feedname, objectid='', manifest=False):
    if manifest:
        _mimetype = 'application/vnd.oasis.taxii+json; version=2.0'
    else:
        _mimetype = 'application/vnd.oasis.stix+json; version=2.0'

    return Response(
        stream_with_context(response_formatter(feedname, objectid, manifest)),
        mimetype=_mimetype
    )
