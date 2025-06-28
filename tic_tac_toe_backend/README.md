# Tic Tac Toe Backend

Backend REST API for Tic Tac Toe multiplayer game built with FastAPI. Handles user registration, authentication, game management, moves, match history, and leaderboard.

## Features

- User registration & login (`/register`, `/login`)
- Game creation & joining (`/games`, `/games/{id}/join`)
- Play moves, view real-time board state (`/games/{id}/move`, `/games/{id}`)
- Fetch move history, match history, leaderboard
- All data persisted in SQLite (see `../tic_tac_toe_database/`)

## Running locally

- Ensure the SQLite DB exists at `../tic_tac_toe_database/tic_tac_toe.db`
- Start application:

```sh
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 3001
```

## Environment Variables

- `TIC_TAC_TOE_DB_PATH` - override for the DB path (default: `../tic_tac_toe_database/tic_tac_toe.db`)

## REST API Endpoints

### Authentication & Users

- `POST /register`: Register a new user, JSON body `{username, password}`
- `POST /login`: Login (returns access token)
- `GET /me`: Get current user info (requires `Authorization: Bearer <access_token>`)

### Games

- `POST /games`: Create a game `{as_player: "X"|"O", opponent_type: "human"|"ai"}`
- `POST /games/{game_id}/join`: Join a waiting game
- `GET /games/{game_id}`: Get current state of a game
- `GET /games`: List all games for user

### Moves

- `POST /games/{game_id}/move`: Play a move, JSON `{position, player_id}`
- `GET /games/{game_id}/moves`: Move history for a game

### Leaderboard & History

- `GET /leaderboard`: Global leaderboard
- `GET /history`: All games for current user

## Notes

- Authorization is token-based using the username (not secure; for demo only)
- To support WebSockets/real-time moves, see `/ws-usage` endpoint for guidance
- Can play "AI" by joining unclaimed side, simple for now (future improvement)
- Match history and leaderboard tables are updated at game conclusion

----

MIT License

