from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, constr
from typing import Optional, List
import sqlite3
import hashlib
import os
import datetime

DATABASE_PATH = os.environ.get("TIC_TAC_TOE_DB_PATH", "../tic_tac_toe_database/tic_tac_toe.db")


app = FastAPI(
    title="Tic Tac Toe Backend",
    description=(
        "REST API backend for Tic Tac Toe game, handling users, games, moves, "
        "history, and leaderboard."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "users", "description": "User registration, login, and profile management"},
        {"name": "games", "description": "Create, join, and play games"},
        {"name": "moves", "description": "Submit moves and game board state"},
        {"name": "leaderboard", "description": "Leaderboard and match history"},
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_db():
    """Context manager for DB connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def hash_password(password: str) -> str:
    """Returns the SHA-256 hash of the password."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


class UserRegister(BaseModel):
    username: constr(min_length=3, max_length=20)
    password: constr(min_length=4, max_length=100)


class UserLogin(UserRegister):
    pass


class UserInfo(BaseModel):
    id: int
    username: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GameCreate(BaseModel):
    as_player: str = Field(..., description="'X' or 'O'")  # Choose which side to play
    opponent_type: str = Field(..., description="'human' or 'ai'")


class GameState(BaseModel):
    id: int
    board_state: str = Field(..., description="Board as string, e.g. 'XOX   O  '")
    status: str
    player_x_id: int
    player_o_id: Optional[int]
    winner: Optional[int]
    created_at: str
    finished_at: Optional[str]


class MoveRequest(BaseModel):
    position: int = Field(..., ge=0, le=8, description="Board index (0-8)")
    player_id: int


class MoveResponse(BaseModel):
    move_index: int
    position: int
    player_id: int
    created_at: str


class LeaderboardEntry(BaseModel):
    user_id: int
    username: str
    wins: int
    losses: int
    draws: int
    last_played: Optional[str]


class MatchHistoryItem(BaseModel):
    game_id: int
    board_state: str
    status: str
    winner: Optional[int]
    created_at: str
    finished_at: Optional[str]


# ------------------------------------
# USERS
# ------------------------------------

# PUBLIC_INTERFACE
@app.post("/register", summary="User registration", tags=["users"])
def register(user: UserRegister):
    """
    Registers a new user.

    - **username:** Username for the new account
    - **password:** Password for the account

    Returns User info.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (user.username, hash_password(user.password))
            )
            conn.commit()
            uid = cur.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username already exists.")
        cur.execute("SELECT id, username, created_at FROM users WHERE id = ?", (uid,))
        row = cur.fetchone()
        return UserInfo(
            id=row[0],
            username=row[1],
            created_at=row[2]
        )


# PUBLIC_INTERFACE
@app.post("/login", summary="User login", tags=["users"], response_model=TokenResponse)
def login(user: UserLogin):
    """
    Login endpoint.

    Returns (mock) access token (username) if credentials are correct.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE username = ?", (user.username,))
        row = cur.fetchone()
        if not row or not verify_password(user.password, row[1]):
            raise HTTPException(status_code=401, detail="Invalid credentials.")
    # For simplicity, we use username as token (stateless, not secure)
    return TokenResponse(access_token=user.username)


# PUBLIC_INTERFACE
@app.get("/me", summary="View current user info", tags=["users"], response_model=UserInfo)
def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Gets info on the current user identified by token (username).

    Returns UserInfo.
    """
    username = token
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, created_at FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        return UserInfo(
            id=row[0],
            username=row[1],
            created_at=row[2]
        )


# ------------------------------------
# GAMES
# ------------------------------------


def get_free_game_for_join(conn, requested_side):
    """Get an open (waiting) game that does not have both players yet and is not finished."""
    cur = conn.cursor()
    if requested_side.upper() == "O":
        cur.execute("SELECT * FROM games WHERE status = 'waiting' AND player_o_id IS NULL")
    else:  # X or default (allow joining as X if O is already filled)
        cur.execute("SELECT * FROM games WHERE status = 'waiting' AND player_x_id IS NULL")
    return cur.fetchone()


def empty_board() -> str:
    """Returns an empty Tic Tac Toe board string."""
    return " " * 9


def check_winner(board: str):
    """Check for winner on board; returns 'X', 'O', or None."""
    wins = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6)
    ]
    for (a, b, c) in wins:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    if " " not in board:
        return "draw"
    return None


# PUBLIC_INTERFACE
@app.post("/games", summary="Create a new game", tags=["games"], response_model=GameState)
def create_game(game_req: GameCreate, token: str = Depends(oauth2_scheme)):
    """
    Create a new game as the current user.

    - **as_player:** "X" or "O"
    - **opponent_type:** "human" or "ai"

    Returns game info.
    """
    username = token
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        user_id = row[0]

        if game_req.as_player.upper() not in ("X", "O"):
            raise HTTPException(status_code=400, detail="Invalid player side. Use 'X' or 'O'.")

        # AI games - reserve slot as necessary
        board_state = empty_board()
        player_x_id = user_id if game_req.as_player.upper() == "X" else None
        player_o_id = user_id if game_req.as_player.upper() == "O" else None

        cur.execute(
            "INSERT INTO games (player_x_id, player_o_id, board_state, status) "
            "VALUES (?, ?, ?, ?)",
            (player_x_id, player_o_id, board_state, "waiting")
        )
        gid = cur.lastrowid
        conn.commit()
        cur.execute("SELECT * FROM games WHERE id = ?", (gid,))
        row = cur.fetchone()
        return GameState(
            id=row[0],
            player_x_id=row[1],
            player_o_id=row[2],
            board_state=row[3],
            status=row[4],
            winner=row[5],
            created_at=row[6],
            finished_at=row[7]
        )


# PUBLIC_INTERFACE
@app.post("/games/{game_id}/join", summary="Join a waiting game", tags=["games"], response_model=GameState)
def join_game(game_id: int, token: str = Depends(oauth2_scheme)):
    """
    Join a waiting game (assign this user as missing player).

    Returns new game state.
    """
    username = token
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = cur.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found.")
        user_id = user_row[0]

        # Check game status and which slot is open
        cur.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Game not found.")
        game = dict(row)
        if game['status'] != 'waiting':
            raise HTTPException(status_code=409, detail="Game is not waiting for a player.")
        player_x_id = game['player_x_id']
        player_o_id = game['player_o_id']
        # Don't allow user to join as both players
        if user_id == player_x_id or user_id == player_o_id:
            raise HTTPException(status_code=409, detail="User already in game.")
        # Fill open slot and mark in_progress
        if player_x_id is None:
            cur.execute(
                "UPDATE games SET player_x_id = ?, status = 'in_progress' "
                "WHERE id = ?",
                (user_id, game_id)
            )
        elif player_o_id is None:
            cur.execute(
                "UPDATE games SET player_o_id = ?, status = 'in_progress' "
                "WHERE id = ?",
                (user_id, game_id)
            )
        else:
            raise HTTPException(status_code=409, detail="Game already full.")
        conn.commit()
        cur.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = cur.fetchone()
        return GameState(
            id=row[0],
            player_x_id=row[1],
            player_o_id=row[2],
            board_state=row[3],
            status=row[4],
            winner=row[5],
            created_at=row[6],
            finished_at=row[7]
        )


# PUBLIC_INTERFACE
@app.get("/games/{game_id}", summary="Get game state", tags=["games"], response_model=GameState)
def get_game_state(game_id: int):
    """
    Returns the current state of the given game ID.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Game not found.")
        return GameState(
            id=row[0],
            player_x_id=row[1],
            player_o_id=row[2],
            board_state=row[3],
            status=row[4],
            winner=row[5],
            created_at=row[6],
            finished_at=row[7]
        )


# PUBLIC_INTERFACE
@app.get("/games", summary="List user's games (most recent first)", tags=["games"], response_model=List[GameState])
def list_games(token: str = Depends(oauth2_scheme)):
    """
    List all games for the authenticated user.

    Returns a list of GameState.
    """
    username = token
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        user_id = row[0]
        cur.execute(
            "SELECT * FROM games WHERE player_x_id = ? OR player_o_id = ? "
            "ORDER BY created_at DESC",
            (user_id, user_id)
        )
        games = []
        for row in cur.fetchall():
            games.append(
                GameState(
                    id=row[0],
                    player_x_id=row[1],
                    player_o_id=row[2],
                    board_state=row[3],
                    status=row[4],
                    winner=row[5],
                    created_at=row[6],
                    finished_at=row[7]
                )
            )
        return games


# ------------------------------------
# MOVES
# ------------------------------------


def side_to_player_id(game_row, side):
    if side == "X":
        return game_row['player_x_id']
    elif side == "O":
        return game_row['player_o_id']
    return None


# PUBLIC_INTERFACE
@app.post("/games/{game_id}/move", summary="Submit a move in the current game", tags=["moves"])
def submit_move(game_id: int, move: MoveRequest, token: str = Depends(oauth2_scheme)):
    """
    Submit a move for a given game.

    - **position:** (0-8), 0 is top-left, 8 is bottom-right
    """
    username = token
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row or row[0] != move.player_id:
            raise HTTPException(status_code=403, detail="Must move as authenticated user.")
        # Load game
        cur.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        g_row = cur.fetchone()
        if not g_row:
            raise HTTPException(status_code=404, detail="Game not found.")
        game = dict(g_row)

        # Game must be in progress
        if game['status'] != 'in_progress':
            raise HTTPException(status_code=409, detail="Game not in progress.")

        board = list(game['board_state'])
        if board[move.position] != " ":
            raise HTTPException(status_code=409, detail="Position already filled.")

        # Determine whose turn (alternate based on move count)
        cur.execute("SELECT COUNT(*) FROM moves WHERE game_id = ?", (game_id,))
        move_count = cur.fetchone()[0]
        turn = "X" if move_count % 2 == 0 else "O"
        expected_player_id = side_to_player_id(game, turn)
        if move.player_id != expected_player_id:
            raise HTTPException(status_code=403, detail="Not your turn.")
        # Place the move
        board[move.position] = turn
        new_board = "".join(board)

        # Update moves
        cur.execute(
            "INSERT INTO moves (game_id, player_id, move_index, position) "
            "VALUES (?, ?, ?, ?)",
            (game_id, move.player_id, move_count + 1, move.position)
        )
        # Check for winner or draw
        result = check_winner(new_board)
        now = datetime.datetime.utcnow().isoformat()
        winner_id = None
        game_status = game['status']
        finished_at = None

        if result == "draw":
            game_status = "finished"
            finished_at = now
        elif result in ("X", "O"):
            game_status = "finished"
            winner_id = side_to_player_id(game, result)
            finished_at = now

        # Update game state
        cur.execute(
            "UPDATE games SET board_state = ?, status = ?, winner = ?, finished_at = ? "
            "WHERE id = ?",
            (new_board, game_status, winner_id, finished_at, game_id)
        )
        conn.commit()

        # If game is finished, update leaderboard
        if game_status == "finished":
            update_leaderboard(cur, game, winner_id, result)
            conn.commit()

        cur.execute(
            "SELECT id, move_index, position, player_id, created_at FROM moves WHERE game_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (game_id,)
        )
        mr = cur.fetchone()
        return {
            "move_index": mr[1],
            "position": mr[2],
            "player_id": mr[3],
            "created_at": mr[4]
        }


def update_leaderboard(cur, game_row, winner_id, result):
    """
    Updates leaderboard table after a finished game.
    """
    ids = [game_row['player_x_id'], game_row['player_o_id']]
    now = datetime.datetime.utcnow().isoformat()
    for uid in ids:
        # Retrieve current
        cur.execute("SELECT wins, losses, draws FROM leaderboard WHERE user_id = ?", (uid,))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO leaderboard (user_id, wins, losses, draws, last_played) "
                "VALUES (?,0,0,0,?)",
                (uid, now)
            )

    # Update
    if result == "draw":
        for uid in ids:
            cur.execute(
                "UPDATE leaderboard SET draws = draws + 1, last_played = ? "
                "WHERE user_id = ?",
                (now, uid)
            )
    elif winner_id is not None:
        loser_id = ids[0] if ids[1] == winner_id else ids[1]
        cur.execute(
            "UPDATE leaderboard SET wins = wins + 1, last_played = ? "
            "WHERE user_id = ?",
            (now, winner_id)
        )
        cur.execute(
            "UPDATE leaderboard SET losses = losses + 1, last_played = ? "
            "WHERE user_id = ?",
            (now, loser_id)
        )


# PUBLIC_INTERFACE
@app.get("/games/{game_id}/moves", summary="Get moves history for a game", tags=["moves"])
def get_move_history(game_id: int):
    """
    Gets the move history for a specific game.

    Returns a list of move objects.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, move_index, position, player_id, created_at FROM moves "
            "WHERE game_id = ? ORDER BY move_index ASC",
            (game_id,)
        )
        results = []
        for row in cur.fetchall():
            results.append({
                "move_index": row[1],
                "position": row[2],
                "player_id": row[3],
                "created_at": row[4]
            })
        return results


# ------------------------------------
# LEADERBOARD & HISTORY
# ------------------------------------


# PUBLIC_INTERFACE
@app.get("/leaderboard", summary="Get global leaderboard", tags=["leaderboard"], response_model=List[LeaderboardEntry])
def get_leaderboard():
    """
    Get leaderboard (sorted by wins).
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT leaderboard.user_id, users.username, leaderboard.wins, leaderboard.losses, "
            "leaderboard.draws, leaderboard.last_played FROM leaderboard JOIN users "
            "ON leaderboard.user_id = users.id "
            "ORDER BY leaderboard.wins DESC, leaderboard.draws DESC"
        )
        results = []
        for row in cur.fetchall():
            results.append(
                LeaderboardEntry(
                    user_id=row[0],
                    username=row[1],
                    wins=row[2],
                    losses=row[3],
                    draws=row[4],
                    last_played=row[5]
                )
            )
        return results


# PUBLIC_INTERFACE
@app.get("/history", summary="Get user's match history", tags=["leaderboard"], response_model=List[MatchHistoryItem])
def get_user_history(token: str = Depends(oauth2_scheme)):
    """
    Returns all matches played by user (sorted by recent first).
    """
    username = token
    with sqlite3.connect(DATABASE_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        user_id = row[0]
        cur.execute(
            "SELECT id, board_state, status, winner, created_at, finished_at FROM games "
            "WHERE player_x_id = ? OR player_o_id = ? "
            "ORDER BY created_at DESC",
            (user_id, user_id)
        )
        results = []
        for r in cur.fetchall():
            results.append(
                MatchHistoryItem(
                    game_id=r[0],
                    board_state=r[1],
                    status=r[2],
                    winner=r[3],
                    created_at=r[4],
                    finished_at=r[5]
                )
            )
        return results


# PUBLIC_INTERFACE
@app.get("/", tags=["users"], summary="Health check")
def health_check():
    """
    Health check endpoint.
    """
    return {"message": "Healthy"}


# Explicitly add an API docs route for WebSocket/real-time (not implemented, usage note).
@app.get("/ws-usage", tags=["games"])
def websocket_usage_note():
    """
    Note: Real-time/multiplayer via WebSockets not implemented in this version.
    """
    return {
        "detail":
        "To implement real-time multiplayer, see FastAPI WebSockets and use /ws endpoints."
    }
