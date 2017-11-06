# -*- coding: utf-8 -*-

#  Copyright 2016 Palo Alto Networks, Inc
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

import os
import os.path
import json

from unittest import TestCase
from nose.tools import assert_items_equal, assert_equal
from parameterized import parameterized

import taxiing.stix

TestCase.maxDiff = None
MYDIR = os.path.dirname(__file__)


def stix_results_file(fname):
    return fname.rsplit('.', 1)[0]+'_result.json'


def load_stix_vectors():
    testfiles = os.listdir(MYDIR)
    testfiles = filter(
        lambda x: x.startswith('stix_package_'),
        testfiles
    )

    testfiles = filter(
        lambda x: os.path.isfile(os.path.join(MYDIR, stix_results_file(x))),
        testfiles
    )

    print 'Loaded {} STIX test packages'.format(len(testfiles))

    return [(os.path.join(MYDIR, testfile),) for testfile in testfiles]


@parameterized(load_stix_vectors)
def test_stixdecoder(testfile):
    with open(testfile, 'r') as f:
        spackage = f.read()

    with open(stix_results_file(testfile)) as f:
        results = json.load(f)

    assert_items_equal(
        taxiing.stix.decode(spackage)[1],
        results
    )


def test_parse_stix_timestamp():
    assert_equal(
        taxiing.stix._parse_stix_timestamp('2017-11-06T12:12:19.000000+00:00'),
        1509970339000
    )
