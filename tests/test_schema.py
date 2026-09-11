"""The schema carries the guarantee that generated additions never masquerade
as source material. These tests hold that line."""

import json

from lectura.schema import Block, BlockType, Flag, Note, Origin


def test_extracted_and_supplements_stay_separate():
    note = Note(
        blocks=[
            Block(type=BlockType.TEXT, content="what the board said"),
            Block(type=BlockType.TEXT, content="helpful aside",
                  origin=Origin.SUPPLEMENT),
        ]
    )
    assert [b.content for b in note.extracted()] == ["what the board said"]
    assert [b.content for b in note.supplements()] == ["helpful aside"]


def test_flagged_block_is_uncertain_regardless_of_confidence():
    block = Block(type=BlockType.EQUATION, content="x=1",
                  confidence=0.99, flags=[Flag.INVALID_LATEX])
    assert block.is_uncertain()


def test_confidence_threshold_governs_review():
    low = Block(type=BlockType.TEXT, content="a", confidence=0.5)
    high = Block(type=BlockType.TEXT, content="b", confidence=0.95)
    note = Note(blocks=[low, high])
    assert note.needs_review() == [low]


def test_missing_confidence_is_not_treated_as_uncertain():
    # Tesseract supplies no confidence; absence must not mean "bad".
    assert not Block(type=BlockType.TEXT, content="a").is_uncertain()


def test_note_round_trips_through_json():
    note = Note(title="T", blocks=[Block(type=BlockType.EQUATION, content=r"\alpha")])
    restored = Note.model_validate(json.loads(note.model_dump_json()))
    assert restored.title == "T"
    assert restored.blocks[0].content == r"\alpha"
    assert restored.schema_version == note.schema_version
