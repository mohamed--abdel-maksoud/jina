from typing import Dict, List

import numpy as np
import pytest

from jina import Document
from jina.drivers.segment import SegmentDriver
from jina.executors.segmenters import BaseSegmenter
from jina.executors.decorators import single
from jina.types.sets import DocumentSet


class MockSegmenter(BaseSegmenter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_keys = {'text'}

    @single
    def segment(self, text: str, *args, **kwargs) -> List[Dict]:
        if text == 'valid':
            # length, parent_id and id are protected keys that won't affect the segments
            return [
                {
                    'blob': np.array([0.0, 0.0, 0.0]),
                    'weight': 0.0,
                    'mime_type': 'text/plain',
                    'tags': {'id': 3},
                },
                {'blob': np.array([1.0, 1.0, 1.0]), 'weight': 1.0, 'tags': {'id': 4}},
                {'blob': np.array([2.0, 2.0, 2.0]), 'weight': 2.0, 'tags': {'id': 5}},
            ]
        else:
            return [{'non_existing_key': 1}]


class SimpleSegmentDriver(SegmentDriver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def exec_fn(self):
        return self._exec_fn


def test_segment_driver():
    valid_doc = Document()
    valid_doc.text = 'valid'
    valid_doc.mime_type = 'image/png'

    driver = SimpleSegmentDriver()
    executor = MockSegmenter()
    driver.attach(executor=executor, runtime=None)
    driver._apply_all(DocumentSet([valid_doc]))

    assert valid_doc.chunks[0].tags['id'] == 3
    assert valid_doc.chunks[0].parent_id == valid_doc.id
    np.testing.assert_equal(valid_doc.chunks[0].blob, np.array([0.0, 0.0, 0.0]))
    assert valid_doc.chunks[0].weight == 0.0
    assert valid_doc.chunks[0].mime_type == 'text/plain'

    assert valid_doc.chunks[1].tags['id'] == 4
    assert valid_doc.chunks[1].parent_id == valid_doc.id
    np.testing.assert_equal(valid_doc.chunks[1].blob, np.array([1.0, 1.0, 1.0]))
    assert valid_doc.chunks[1].weight == 1.0
    assert valid_doc.chunks[1].mime_type == 'image/png'

    assert valid_doc.chunks[2].tags['id'] == 5
    assert valid_doc.chunks[2].parent_id == valid_doc.id
    np.testing.assert_equal(valid_doc.chunks[2].blob, np.array([2.0, 2.0, 2.0]))
    assert valid_doc.chunks[2].weight == 2.0
    assert valid_doc.chunks[2].mime_type == 'image/png'


def test_chunks_exist_already():
    document = Document(
        text='valid', chunks=[Document(text='test2'), Document(text='test3')]
    )
    # before segmentation
    assert len(document.chunks) == 2
    for chunk in document.chunks:
        assert chunk.parent_id == document.id
        assert chunk.siblings == 2

    driver = SimpleSegmentDriver()
    executor = MockSegmenter()
    driver.attach(executor=executor, runtime=None)
    driver._apply_all(DocumentSet([document]))

    # after segmentation
    assert len(document.chunks) == 5
    for chunk in document.chunks:
        assert chunk.parent_id == document.id
        assert chunk.siblings == 5


def test_broken_document():
    driver = SimpleSegmentDriver()
    executor = MockSegmenter()
    driver.attach(executor=executor, runtime=None)

    invalid_doc = Document()
    invalid_doc.id = 1
    invalid_doc.text = 'invalid'

    with pytest.raises(AttributeError):
        driver._apply_all([DocumentSet([invalid_doc])])
