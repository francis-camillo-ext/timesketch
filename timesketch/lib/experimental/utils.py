# Copyright 2017 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utilities for generating graphs from elasticsearch data."""

# pylint: skip-file
import sys

from flask import current_app

from timesketch.lib.datastores.elastic import ElasticsearchDataStore
from timesketch.models.sketch import Sketch
from xml.etree import ElementTree

# TODO: Just for testing, remove as soon as graph analyzers are implemented.
GRAPH_VIEWS = [
    {
        u'name': u'Entire graph',
        u'description': u'Show the entire graph.',
        u'labels': [u'Browser'],
        u'supported_os': [u'Darwin', u'Linux', u'Windows'],
        u'form_data': {},
        u'query': u'MATCH (:Sketch{sketch_id:{sketch_id}})<-[:HAS]-(a)-[b]->(c) RETURN *'
    },
    {
        u'name': u'Windows interactive logins',
        u'description': u'Windows interactive logins.',
        u'labels': [],
        u'supported_os': [u'Windows'],
        u'form_data': {
            u'username': {
                u'label': u'Username',
                u'value': u'',
                u'type': u'text',
                u'validation': {u'required': True},
            },
            u'machine': {
                u'label': u'Machine',
                u'value': u'',
                u'type': u'text',
                u'validation': {u'required': False},
            }
        },
        u'query': u'MATCH (:Sketch{sketch_id:{sketch_id}})<-[:HAS]-(user:WindowsADUser)-[r1:ACCESS]->(m1:WindowsMachine) WHERE r1.method = "Interactive" AND user.username = {username} RETURN *'
    },
    {
        u'name': u'All Windows logins',
        u'description': u'Windows interactive logins.',
        u'labels': [],
        u'supported_os': [u'Windows'],
        u'form_data': {},
        u'query': u'MATCH (:Sketch{sketch_id:{sketch_id}})<-[:HAS]-(user:WindowsADUser)-[r1:ACCESS]->(m1:WindowsMachine) RETURN *'
    },
]


def event_stream(sketch_id, query):
    es = ElasticsearchDataStore(
        host=current_app.config[u'ELASTIC_HOST'],
        port=current_app.config[u'ELASTIC_PORT'])
    sketch = Sketch.query.get(sketch_id)
    if not sketch:
        sys.exit('No such sketch')
    indices = {t.searchindex.index_name for t in sketch.timelines}

    result = es.search(
        sketch_id=sketch_id,
        query_string=query,
        query_filter={u'limit': 10000},
        query_dsl={},
        indices=[u'_all'],
        return_fields=[u'xml_string', u'timestamp'],
        enable_scroll=True)

    scroll_id = result[u'_scroll_id']
    scroll_size = result[u'hits'][u'total']

    for event in result[u'hits'][u'hits']:
        yield event

    while scroll_size > 0:
        result = es.client.scroll(scroll_id=scroll_id, scroll=u'1m')
        scroll_id = result[u'_scroll_id']
        scroll_size = len(result[u'hits'][u'hits'])
        for event in result[u'hits'][u'hits']:
            yield event


def parse_xml_event(event_xml):
    xml_root = ElementTree.fromstring(event_xml)
    base = u'.//{http://schemas.microsoft.com/win/2004/08/events/event}'
    event_container = {u'System': {}, u'EventData': {}}

    def _sanitize_event_value(value):
        none_values = [u'-', u' ']
        if value in none_values:
            return None
        return value

    for child in xml_root.find(u'{0:s}System'.format(base)):
        element_name = child.tag.split(u'}')[1]
        element_value = _sanitize_event_value(child.text)
        event_container[u'System'][element_name] = {u'value': element_value}
        event_container[u'System'][element_name][u'attributes'] = child.attrib

    for child in xml_root.find(u'{0:s}EventData'.format(base)):
        element_name = child.get(u'Name')
        element_value = _sanitize_event_value(child.text)
        event_container[u'EventData'][element_name] = element_value

    return event_container


def get_graph_views():
    views = []

    for index, view in enumerate(GRAPH_VIEWS):
        view[u'id'] = index
        views.append(view)

    return views


def get_graph_view(view_id):
    return GRAPH_VIEWS[view_id]

