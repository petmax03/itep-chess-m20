"""Recover native castling flags from the operator's complete move history."""
import chess


def native_castling_words(board):
    """Return (Rok words by color, colors with unknown initial history).

    Native Rok bit 2 distinguishes a king that has not castled (including
    lost rights) from one that has castled. FEN alone cannot encode that fact.
    For an ambiguous initial FEN preserve v09's zero service bit and report
    the uncertainty. Normal games from the initial position are unambiguous.
    """
    cursor = board.root()
    castled = {
        color: False if cursor.has_castling_rights(color) else None
        for color in (chess.WHITE, chess.BLACK)
    }
    for move in board.move_stack:
        if cursor.is_castling(move):
            castled[cursor.turn] = True
        cursor.push(move)
    words = {}
    unknown = []
    for color, name in [(chess.WHITE, "white"), (chess.BLACK, "black")]:
        k = board.has_kingside_castling_rights(color)
        q = board.has_queenside_castling_rights(color)
        if castled[color] is None:
            unknown.append(name)
        service = 4 if castled[color] is False else 0
        words[color] = service | int(k) | (int(q) << 1)
    return words, unknown
