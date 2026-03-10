from dataclasses import dataclass


@dataclass(slots=True)
class ChunkEntity:
    id: str
    file_id: str
    page: int
    paragraph_id: str
    block_type: str
    chunk_index: int
    chunk_text: str
    source_offset: int
    metadata_json: str
