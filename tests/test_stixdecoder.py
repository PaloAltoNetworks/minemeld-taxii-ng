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

from __future__ import print_function

import os
import os.path
import json

from unittest import TestCase
from nose.tools import assert_items_equal, assert_equal
from parameterized import parameterized

import taxiing.stix.v1
import taxiing.stix.v2
import taxiing.stix

TestCase.maxDiff = None
MYDIR = os.path.dirname(__file__)


def stix_results_file(fname):
    return fname.rsplit('.', 1)[0]+'_result.json'


def has_result_file(tname):
    return os.path.isfile(os.path.join(MYDIR, stix_results_file(tname)))


def load_stix_v2_vectors():
    testfiles = os.listdir(MYDIR)
    testfiles = filter(
        lambda x: x.startswith('stix_v2_package_'),
        testfiles
    )

    testfiles = filter(
        has_result_file,
        testfiles
    )

    print("Loaded {} STIX v2 Test packages".format(len(testfiles)))

    return [(os.path.join(MYDIR, testfile),) for testfile in testfiles]


def load_stix_v1_vectors():
    testfiles = os.listdir(MYDIR)
    testfiles = filter(
        lambda x: x.startswith('stix_package_'),
        testfiles
    )

    testfiles = filter(
        has_result_file,
        testfiles
    )

    print('Loaded {} STIX test packages'.format(len(testfiles)))

    return [(os.path.join(MYDIR, testfile),) for testfile in testfiles]


@parameterized(load_stix_v1_vectors, skip_on_empty=True)
def test_stix_v1_decoder(testfile):
    with open(testfile, 'r') as f:
        spackage = f.read()

    with open(stix_results_file(testfile)) as f:
        results = json.load(f)

    assert_items_equal(
        taxiing.stix.v1.decode(spackage)[1],
        results
    )


@parameterized(load_stix_v2_vectors, skip_on_empty=True)
def test_stix_v2_decoder(testfile):
    with open(testfile, 'r') as f:
        spackage = f.read()

    try:
        with open(stix_results_file(testfile)) as f:
            results = json.load(f)

    except IOError:
        print('Creating {}...'.format(stix_results_file(testfile)))
        with open(stix_results_file(testfile), 'w+') as f:
            json.dump(
                taxiing.stix.v2.decode(spackage)[1],
                f,
                indent=4,
                sort_keys=True
            )

        with open(stix_results_file(testfile)) as f:
            results = json.load(f)

    assert_items_equal(
        taxiing.stix.v2.decode(spackage)[1],
        results
    )


def test_parse_stix_timestamp():
    assert_equal(
        taxiing.stix.parse_stix_timestamp('2017-11-06T12:12:19.000000+00:00'),
        1509970339000
    )
