import json
import logging

from .. import parse_stix_timestamp


LOG = logging.getLogger(__name__)


TLP_MARKING_DEFINITIONS = {
    'marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9': 'white',
    'marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da': 'green',
    'marking-definition--f88d31f6-486f-44da-b317-01333bde0b82': 'amber',
    'marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed': 'red'
}


def stix2_tlp(markings):
    for m in markings:
        if m in TLP_MARKING_DEFINITIONS:
            return TLP_MARKING_DEFINITIONS[m]

    return None


_stix2_attr_tansforms = {
    'id': 'stix2_id',
    'name': 'stix2_name',
    'pattern': 'indicator',
    'labels': 'stix2_labels',
    'created': ('first_seen', parse_stix_timestamp),
    'valid_from': ('stix2_created', parse_stix_timestamp),
    'modified': ('stix2_modified', parse_stix_timestamp),
    'created_by_ref': '_created_by_ref',
    'object_marking_refs': ('share_level', stix2_tlp)
}


def decode(content, **kwargs):
    latest_timestamp = 0
    indicators = []
    identities = {}

    try:
        bundle = json.loads(content)
    except Exception:
        LOG.exception('Error in decoding STIX2 Json')
        return 0, []

    type_ = bundle.get("type", None)
    if not type_ or type_ != 'bundle':
        raise RuntimeError("Content is not a STIX2 bundle")

    objects = bundle.get("objects", [])
    for o in objects:
        type_ = o.get('type', None)

        if type_ is None:
            continue

        if type_ == 'identity':
            identities[o['id']] = '{}:{}'.format(
                o.get('identity_class', 'unknown'),
                o.get('name', 'unknown')
            )
            continue

        if type_ != 'indicator':
            continue

        indicator = dict(type="stix2-pattern")

        for a, v in o.iteritems():
            xform = _stix2_attr_tansforms.get(a, None)
            if xform is None:
                continue

            if isinstance(xform, str):
                indicator[xform] = v
                continue

            xformed = xform[1](v)
            if xformed is not None:
                indicator[xform[0]] = xformed

        indicators.append(indicator)

    for i in indicators:
        # fix identity refs
        cbr = i.pop('_created_by_ref', None)
        if cbr is not None:
            i['stix2_created_by'] = identities[cbr]

        for ts in ['first_seen', 'stix2_created', 'stix2_modified']:
            tsv = indicator.get(ts, 0)
            if tsv > latest_timestamp:
                latest_timestamp = tsv

    return latest_timestamp, indicators
