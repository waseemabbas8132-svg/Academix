from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class SimilarityMatch:
    other_submission_id: str
    score: float
    matching_segments: tuple[str, ...]


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def compare_answers(
    submission_id: str,
    text: str,
    peers: list[tuple[str, str]],
    *,
    threshold: float = 0.72,
    max_tokens: int = 1200,
) -> tuple[SimilarityMatch, ...]:
    current_tokens = _tokens(text)[:max_tokens]
    if len(current_tokens) < 8:
        return ()

    matches: list[SimilarityMatch] = []
    for peer_id, peer_text in peers:
        if peer_id == submission_id:
            continue
        peer_tokens = _tokens(peer_text)[:max_tokens]
        if len(peer_tokens) < 8:
            continue
        score = SequenceMatcher(
            a=current_tokens,
            b=peer_tokens,
            autojunk=False,
        ).ratio()
        if score < threshold:
            continue
        matching_segments = tuple(
            " ".join(current_tokens[block.a : block.a + block.size])
            for block in SequenceMatcher(
                a=current_tokens,
                b=peer_tokens,
                autojunk=False,
            ).get_matching_blocks()
            if block.size >= 5
        )
        matches.append(
            SimilarityMatch(
                other_submission_id=peer_id,
                score=score,
                matching_segments=matching_segments,
            )
        )
    return tuple(sorted(matches, key=lambda match: match.score, reverse=True))
