import logging
import os
import collections
from datetime import datetime, timedelta

import pytz
import yaml
import requests
import bs4  # we use bs4 to parse the HTML page
from lxml import etree

from minemeld.ft.basepoller import BasePollerFT
from minemeld.ft.utils import interval_in_sec

from .taxii import v11 as taxii11
from .stix import decode as stix_decode

LOG = logging.getLogger(__name__)


class Miner(BasePollerFT):
    def __init__(self, name, chassis, config):
        self.discovered_poll_service = None
        self.last_taxii_run = None
        self.last_stix_package_ts = None
        self.last_taxii_content_ts = None
        self.api_key = None

        super(Miner, self).__init__(name, chassis, config)

    def configure(self):
        super(Miner, self).configure()

        self.verify_cert = self.config.get('verify_cert', True)
        self.polling_timeout = self.config.get('polling_timeout', 20)

        self.initial_interval = self.config.get('initial_interval', '1d')
        self.initial_interval = interval_in_sec(self.initial_interval)
        if self.initial_interval is None:
            LOG.error(
                '%s - wrong initial_interval format: %s',
                self.name, self.initial_interval
            )
            self.initial_interval = 86400
        self.max_poll_dt = self.config.get(
            'max_poll_dt',
            86400
        )

        # options for processing
        self.ip_version_auto_detect = self.config.get('ip_version_auto_detect', True)
        self.ignore_composition_operator = self.config.get('ignore_composition_operator', False)
        self.create_fake_indicator = self.config.get('create_fake_indicator', False)
        self.lower_timestamp_precision = self.config.get('lower_timestamp_precision', False)

        self.discovery_service = self.config.get('discovery_service', None)
        self.poll_service = self.config.get('poll_service', None)
        self.collection = self.config.get('collection', None)

        self.side_config_path = os.path.join(
            os.environ['MM_CONFIG_DIR'],
            '%s_side_config.yml' % self.name
        )

        self.prefix = self.config.get('prefix', None)

        self.confidence_map = self.config.get('confidence_map', {
            'low': 40,
            'medium': 60,
            'high': 80
        })

        # authentication
        self.api_key = self.config.get('api_key', None)
        self.api_header = self.config.get('api_header', None)
        self.username = self.config.get('username', None)
        self.password = self.config.get('password', None)

        self._load_side_config()

    def _load_side_config(self):
        try:
            with open(self.side_config_path, 'r') as f:
                sconfig = yaml.safe_load(f)

        except Exception as e:
            LOG.error('%s - Error loading side config: %s', self.name, str(e))
            return

        api_key = sconfig.get('api_key', None)
        api_header = sconfig.get('api_header', None)
        if api_key is not None and api_header is not None:
            self.api_key = api_key
            self.api_header = api_header
            LOG.info('{} - Loaded API credentials from side config'.format(self.name))

        username = sconfig.get('username', None)
        password = sconfig.get('password', None)
        if username is not None and password is not None:
            self.username = username
            self.password = password
            LOG.info('{} - Loaded Basic authentication credentials from side config'.format(self.name))

        verify_cert = sconfig.get('verify_cert', None)
        if verify_cert is not None:
            self.verify_cert = verify_cert
            LOG.info('{} - Loaded verify cert from side config'.format(self.name))

    def _saved_state_restore(self, saved_state):
        super(Miner, self)._saved_state_restore(saved_state)
        self.last_taxii_run = saved_state.get('last_taxii_run', None)
        LOG.info('last_taxii_run from sstate: %s', self.last_taxii_run)

    def _saved_state_create(self):
        sstate = super(Miner, self)._saved_state_create()
        sstate['last_taxii_run'] = self.last_taxii_run

        return sstate

    def _saved_state_reset(self):
        super(Miner, self)._saved_state_reset()
        self.last_taxii_run = None

    def _process_item(self, item):
        indicator = item.pop('indicator')
        value = {}
        for k, v in item.iteritems():
            if k.startswith('stix_') and self.prefix is not None:
                k = self.prefix + k[4:]
            value[k] = v

        return [[indicator, value]]

    def _send_request(self, url, headers, data, stream=False):
        if self.api_key is not None and self.api_header is not None:
            headers[self.api_header] = self.api_key

        rkwargs = dict(
            stream=stream,
            verify=self.verify_cert,
            timeout=self.polling_timeout,
            headers=headers,
            data=data
        )

        if self.username is not None and self.password is not None:
            rkwargs['auth'] = (self.username, self.password)

        LOG.debug('{} - request to {!r}: {!r}'.format(self.name, url, rkwargs))

        r = requests.post(
            url,
            **rkwargs
        )

        try:
            r.raise_for_status()
        except Exception:
            LOG.debug(
                '{} - exception in request: {!r} {!r}'.format(self.name, r.status_code, r.content)
            )
            raise

        return r

    def _raise_for_taxii_error(self, response):
        if response.contents[0].name != 'Status_Message':
            return

        if response.contents[0]['status_type'] == 'SUCCESS':
            return

        raise RuntimeError('{} - error returned by TAXII Server: {}'.format(
            self.name, response.contents[0]['status_type']
        ))

    def _discover_poll_service(self):
        # let's start from discovering the available services
        req = taxii11.discovery_request()
        LOG.debug('protocol {!r}'.format(self.discovery_service.split(':', 1)[0]))
        reqhdrs = taxii11.headers(
            protocol=self.discovery_service.split(':', 1)[0]
        )
        result = self._send_request(
            url=self.discovery_service,
            headers=reqhdrs,
            data=req
        )

        LOG.debug('{} - Discovery response: {!r}'.format(self.name, result.text))

        result = bs4.BeautifulSoup(result.text, 'xml')
        self._raise_for_taxii_error(result)

        # from here we look for a good collection management service
        coll_services = result.find_all(
            'Service_Instance',
            service_type='COLLECTION_MANAGEMENT'
        )
        if len(coll_services) == 0:
            raise RuntimeError('{} - Collection management service not found'.format(self.name))

        selected_coll_service = None
        for coll_service in coll_services:
            address = coll_service.find('Address')
            if address is None:
                LOG.error(
                    '{} - Collection management service with no address: {!r}'.format(
                        self.name, coll_service
                    )
                )
                continue
            address = address.string

            if selected_coll_service is None:
                selected_coll_service = address
                continue

            msgbindings = coll_service.find_all('Message_Binding')
            if len(msgbindings) != 0:
                for msgbinding in msgbindings:
                    if msgbinding.string == taxii11.MESSAGE_BINDING:
                        selected_coll_service = address
                        break

        if selected_coll_service is None:
            raise RuntimeError(
                '{} - Collection management service not found'.format(self.name)
            )

        # from here we look for the correct poll service
        req = taxii11.collection_information_request()
        reqhdrs = taxii11.headers(
            protocol=selected_coll_service.split(':', 1)[0]
        )
        result = self._send_request(
            url=selected_coll_service,
            headers=reqhdrs,
            data=req
        )

        LOG.debug('{} - Collection information response: {!r}'.format(self.name, result.text))

        result = bs4.BeautifulSoup(result.text, 'xml')
        self._raise_for_taxii_error(result)

        # from here we look for the collection
        collections = result.find_all('Collection', collection_name=self.collection)
        if len(collections) == 0:
            raise RuntimeError('{} - collection {} not found'.format(self.name, self.collection))

        # and the right poll service
        poll_service = None
        for coll in collections:
            pservice = coll.find('Polling_Service')
            if pservice is None:
                LOG.error('{} - Collection with no Polling_Service: {!r}'.format(self.name, coll))
                continue

            address = pservice.find('Address')
            if address is None:
                LOG.error('{} - Collection with no Address: {!r}'.format(self.name, coll))
                continue
            address = address.string

            if poll_service is None:
                poll_service = address
                continue

            msgbindings = coll_service.find_all('Message_Binding')
            if len(msgbindings) != 0:
                for msgbinding in msgbindings:
                    if msgbinding.string == taxii11.MESSAGE_BINDING:
                        poll_service = address
                        break

        if poll_service is None:
            raise RuntimeError('{} - No valid Polling Service found'.format(self.name))

        return poll_service

    def _poll_collection(self, poll_service, begin, end):
        req = taxii11.poll_request(
            collection_name=self.collection,
            exclusive_begin_timestamp=begin,
            inclusive_end_timestamp=end
        )
        LOG.debug('{} - poll request: {}'.format(self.name, req))
        reqhdrs = taxii11.headers(
            protocol=poll_service.split(':', 1)[0]
        )
        result = self._send_request(
            url=poll_service,
            headers=reqhdrs,
            data=req,
            stream=True
        )

        while True:
            result_part_number = None
            result_id = None
            more = None
            tag_stack = collections.deque()
            try:
                for action, element in etree.iterparse(result.raw, events=('start', 'end'), recover=True):
                    if action == 'start':
                        tag_stack.append(element.tag)

                    else:
                        last_tag = tag_stack.pop()
                        if last_tag != element.tag:
                            raise RuntimeError('{} - error parsing poll response, mismatched tags'.format(self.name))

                    if action == 'end' and element.tag.endswith('Status_Message') and len(tag_stack) == 0:
                        self._raise_for_taxii_error(
                            bs4.BeautifulSoup(etree.tostring(element, encoding='unicode'), 'xml')
                        )
                        return

                    elif action == 'end' and element.tag.endswith('Poll_Response') and len(tag_stack) == 0:
                        result_id = element.get('result_id', None)
                        more = element.get('more', None)
                        result_part_number = element.get('result_part_number', None)
                        if result_part_number is not None:
                            result_part_number = int(result_part_number)

                    elif action == 'end' and element.tag.endswith('Content_Block') and len(tag_stack) == 1:
                        for c in element:
                            if c.tag.endswith('Content'):
                                if len(c) == 0:
                                    LOG.error('{} - Content with no children'.format(self.name))
                                    continue

                                content = etree.tostring(c[0], encoding='unicode')

                                timestamp, indicators = stix_decode(content)
                                for indicator in indicators:
                                    yield indicator

                                if self.last_stix_package_ts is None or timestamp > self.last_stix_package_ts:
                                    LOG.debug('{} - last package ts: {!r}'.format(self.name, timestamp))
                                    self.last_stix_package_ts = timestamp

                            elif c.tag.endswith('Timestamp_Label'):
                                LOG.debug('{} - timestamp label: {!r}'.format(self.name, c.text))
                                timestamp = taxii11.parse_timestamp_label(c.text)
                                LOG.debug('{} - timestamp label: {!r}'.format(self.name, timestamp))

                                if self.last_taxii_content_ts is None or timestamp > self.last_taxii_content_ts:
                                    LOG.debug('{} - last content ts: {!r}'.format(self.name, timestamp))
                                    self.last_taxii_content_ts = timestamp

                        element.clear()

            finally:
                result.close()

            LOG.debug('{} - result_id: {} more: {}'.format(self.name, result_id, more))

            if not more or more == '0' or more.lower() == 'false':
                break

            if result_id is None or result_part_number is None:
                LOG.error('{} - More set to true but no result_id or result_part_number'.format(self.name))
                break

            req = taxii11.poll_fulfillment_request(
                collection_name=self.collection,
                result_id=result_id,
                result_part_number=result_part_number+1
            )
            result = self._send_request(
                url=poll_service,
                headers=reqhdrs,
                data=req,
                stream=True
            )

    def _incremental_poll_collection(self, poll_service, begin, end):
        cbegin = begin
        dt = timedelta(seconds=self.max_poll_dt)

        self.last_stix_package_ts = None
        self.last_taxii_content_ts = None

        while cbegin < end:
            cend = min(end, cbegin+dt)

            LOG.info('{} - polling {!r} to {!r}'.format(self.name, cbegin, cend))
            result = self._poll_collection(
                poll_service=poll_service,
                begin=cbegin,
                end=cend
            )

            for i in result:
                yield i

            if self.last_taxii_content_ts is not None:
                self.last_taxii_run = self.last_taxii_content_ts

            cbegin = cend

    def _build_iterator(self, now):
        if self.poll_service is not None:
            discovered_poll_service = self.poll_service
        else:
            discovered_poll_service = self._discover_poll_service()

        LOG.debug('{} - poll service: {!r}'.format(self.name, discovered_poll_service))

        last_run = self.last_taxii_run
        if last_run is None:
            last_run = now-(self.initial_interval*1000)

        begin = datetime.utcfromtimestamp(last_run/1000)
        begin = begin.replace(microsecond=0, tzinfo=pytz.UTC)

        end = datetime.utcfromtimestamp(now/1000)
        end = end.replace(tzinfo=pytz.UTC)

        if self.lower_timestamp_precision:
            end = end.replace(second=0, microsecond=0)
            begin = begin.replace(second=0, microsecond=0)

        return self._incremental_poll_collection(
            discovered_poll_service,
            begin=begin,
            end=end
        )

    def _flush(self):
        self.last_taxii_run = None
        super(Miner, self)._flush()

    def hup(self, source=None):
        LOG.info('%s - hup received, reload side config', self.name)
        self._load_side_config()
        super(Miner, self).hup(source)

    @staticmethod
    def gc(name, config=None):
        BasePollerFT.gc(name, config=config)

        side_config_path = None
        if config is not None:
            side_config_path = config.get('side_config', None)
        if side_config_path is None:
            side_config_path = os.path.join(
                os.environ['MM_CONFIG_DIR'],
                '{}_side_config.yml'.format(name)
            )

        try:
            os.remove(side_config_path)
        except Exception:
            pass
