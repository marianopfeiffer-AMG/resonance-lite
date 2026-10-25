"""Take selection for Suno playlists (2 takes per track), by dynamic programming.

Each track has candidate takes with (head_db, tail_db) levels. The chosen path minimizes the
largest level jump across track joins, so no transition makes the listener flinch.
"""

from dataclasses import dataclass

MAX_JUMP_DB = 6.0


@dataclass
class Choice:
    takes: list[int]
    max_jump_db: float
    worst_join: int | None  # index i of the join between track i and i+1


def choose_takes(levels: list[list[tuple[float, float]]]) -> Choice:
    """levels[i][k] = (head_db, tail_db) of take k of track i."""
    if not levels:
        return Choice([], 0.0, None)
    best: list[list[float]] = [[0.0] * len(levels[0])]
    back: list[list[int]] = [[-1] * len(levels[0])]
    for i in range(1, len(levels)):
        row, ptr = [], []
        for head, _ in levels[i]:
            options = [
                max(best[i - 1][j], abs(levels[i - 1][j][1] - head))
                for j in range(len(levels[i - 1]))
            ]
            j = min(range(len(options)), key=options.__getitem__)
            row.append(options[j])
            ptr.append(j)
        best.append(row)
        back.append(ptr)
    k = min(range(len(best[-1])), key=best[-1].__getitem__)
    takes = [k]
    for i in range(len(levels) - 1, 0, -1):
        k = back[i][k]
        takes.append(k)
    takes.reverse()
    jumps = [
        abs(levels[i][takes[i]][1] - levels[i + 1][takes[i + 1]][0]) for i in range(len(levels) - 1)
    ]
    worst = max(range(len(jumps)), key=jumps.__getitem__) if jumps else None
    return Choice(takes, max(jumps, default=0.0), worst)
