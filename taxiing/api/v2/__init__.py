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

from flask import request, jsonify
from flask_login import current_user

from .utils import get_taxii2_feeds
from .collection import generate_taxii2_collection


def get_taxii2_server():
    taxii_feeds = get_taxii2_feeds()
    authorized = next(
        (tf for tf in taxii_feeds if current_user.check_feed(tf['name'])),
        None
    )
    if authorized is None:
        return 'Unauthorized', 401

    api_root = 'https://{}api/'.format(request.base_url.split('://', 1)[1])
    response = jsonify(
        title='MineMeld TAXII Server',
        description='TAXII Server powered by MineMeld',
        default=api_root,
        api_roots=[api_root]
    )
    response.headers['Content-Type'] = 'application/vnd.oasis.taxii+json; version=2.0'
    return response


def get_apiroot():
    taxii_feeds = get_taxii2_feeds()
    authorized = next(
        (tf for tf in taxii_feeds if current_user.check_feed(tf['name'])),
        None
    )
    if authorized is None:
        return 'Unauthorized', 401

    response = jsonify(
        title='MineMeld TAXII Server API',
        description='TAXII Server API powered by MineMeld',
        versions=['taxii-2.0'],
        max_content_length=1024
    )
    response.headers['Content-Type'] = 'application/vnd.oasis.taxii+json; version=2.0'
    return response


def get_collections():
    taxii_feeds = get_taxii2_feeds()
    authorized = [tf for tf in taxii_feeds if current_user.check_feed(tf['name'])]
    if len(authorized) == 0:
        return 'Unauthorized', 401

    response = jsonify(collections=[dict(title=feed['name'], id=feed['taxii2_id'], can_read=True, can_write=False) for feed in authorized])
    response.headers['Content-Type'] = 'application/vnd.oasis.taxii+json; version=2.0'
    return response


def get_collection(collection):
    taxii_feeds = get_taxii2_feeds()
    authorized = [tf for tf in taxii_feeds if current_user.check_feed(tf['name'])]
    if len(authorized) == 0:
        return 'Unauthorized', 401

    collection_details = next(
        (c for c in authorized if c['taxii2_id'] == collection),
        None
    )
    if collection_details is None:
        return 'Unauthorized', 401

    response = jsonify(title=collection_details['name'], id=collection_details['taxii2_id'], can_read=True, can_write=False)
    response.headers['Content-Type'] = 'application/vnd.oasis.taxii+json; version=2.0'
    return response


def get_collection_objects(collection):
    taxii_feeds = get_taxii2_feeds()
    authorized = [tf for tf in taxii_feeds if current_user.check_feed(tf['name'])]
    if len(authorized) == 0:
        return 'Unauthorized', 401

    collection_details = next(
        (c for c in authorized if c['taxii2_id'] == collection),
        None
    )
    if collection_details is None:
        return 'Unauthorized', 401

    return generate_taxii2_collection(collection_details['name'], None, False)


def get_collection_object(collection, objectid):
    taxii_feeds = get_taxii2_feeds()
    authorized = [tf for tf in taxii_feeds if current_user.check_feed(tf['name'])]
    if len(authorized) == 0:
        return 'Unauthorized', 401

    collection_details = next(
        (c for c in authorized if c['taxii2_id'] == collection),
        None
    )
    if collection_details is None:
        return 'Unauthorized', 401

    return generate_taxii2_collection(collection_details['name'], objectid, False)


def get_collection_manifest(collection):
    taxii_feeds = get_taxii2_feeds()
    authorized = [tf for tf in taxii_feeds if current_user.check_feed(tf['name'])]
    if len(authorized) == 0:
        return 'Unauthorized', 401

    collection_details = next(
        (c for c in authorized if c['taxii2_id'] == collection),
        None
    )
    if collection_details is None:
        return 'Unauthorized', 401

    return generate_taxii2_collection(collection_details['name'], None, True)
