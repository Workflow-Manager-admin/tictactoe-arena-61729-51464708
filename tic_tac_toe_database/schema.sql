-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Games table
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_x_id INTEGER NOT NULL,
    player_o_id INTEGER,
    board_state TEXT NOT NULL,
    status TEXT NOT NULL, -- 'waiting', 'in_progress', 'finished'
    winner INTEGER, -- user id or NULL if draw
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    FOREIGN KEY(player_x_id) REFERENCES users(id),
    FOREIGN KEY(player_o_id) REFERENCES users(id)
);

-- Moves history table
CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    move_index INTEGER NOT NULL,
    position INTEGER NOT NULL, -- 0-8 for board cell
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(game_id) REFERENCES games(id),
    FOREIGN KEY(player_id) REFERENCES users(id)
);

-- Leaderboard (denormalized, recomputed or updated as games finish)
CREATE TABLE IF NOT EXISTS leaderboard (
    user_id INTEGER PRIMARY KEY,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    last_played TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
