"""The Merkle tree of an anchor, written so that a third party can recompute it with any SHA-256 tool.

* leaf  = SHA-256(0x00 || media id (16 bytes, RFC 4122 order) || media SHA-256 (32 bytes))
* node  = SHA-256(0x01 || left || right); on a level with an odd count, the last node goes up unchanged.
* root  = the last remaining node, in lowercase hex.
* proof = the sibling hashes from the leaf up, each with its side (``left``: the sibling comes first).
"""

import hashlib
import uuid
from typing import Literal, TypedDict

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


class Step(TypedDict):
    side: Literal["left", "right"]
    hash: str


def leaf_hash(media_id: uuid.UUID, sha256_hex: str) -> bytes:
    return hashlib.sha256(LEAF_PREFIX + media_id.bytes + bytes.fromhex(sha256_hex)).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def _levels(leaves: list[bytes]) -> list[list[bytes]]:
    if not leaves:
        raise ValueError("an empty tree has no root")
    levels = [leaves]
    while len(levels[-1]) > 1:
        level = levels[-1]
        up = [_node(level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            up.append(level[-1])
        levels.append(up)
    return levels


def root(leaves: list[bytes]) -> str:
    return _levels(leaves)[-1][0].hex()


def proof(leaves: list[bytes], index: int) -> list[Step]:
    steps: list[Step] = []
    for level in _levels(leaves)[:-1]:
        sibling = index ^ 1
        if sibling < len(level):
            steps.append({"side": "left" if sibling < index else "right", "hash": level[sibling].hex()})
        index //= 2
    return steps


def root_from_proof(leaf: bytes, steps: list[Step]) -> str:
    node = leaf
    for step in steps:
        other = bytes.fromhex(step["hash"])
        node = _node(other, node) if step["side"] == "left" else _node(node, other)
    return node.hex()
