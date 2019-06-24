def blueprint():
    from minemeld.flask import aaa, config  # pylint: disable E0401

    bp = aaa.MMBlueprint('taxiing', __name__, url_prefix='/taxiing')

    if config.get('TAXIING_ENABLE_TAXII1_STIX2_POLL', False):
        from .v1 import poll

        bp.route(
            '/v1/poll', methods=['POST'], feeds=True, read_write=False
        )(poll)

    return bp
