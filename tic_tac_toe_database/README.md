# tic_tac_toe_database

SQLite-based database for Tic Tac Toe application.

## Schema

- `users`: Stores user credentials and profile info
- `games`: Stores game state and player info
- `moves`: Stores move history for each game
- `leaderboard`: Aggregated win/loss/draw info

## Development

To create the database locally:
```sh
python init_db.py
```

- The backend should connect to `tic_tac_toe.db` using SQLite.
- For production, consider switching to PostgreSQL or other RDBMS; adjust schema and backend connector accordingly.

## Files

- `schema.sql`: SQL statements to create all necessary tables
- `init_db.py`: Script to initialize (and re-initialize) the SQLite DB

## Integration

The FastAPI backend container (`tic_tac_toe_backend`) should use this database for:
- User registration and login
- Storing & retrieving game state
- Recording move history and leaderboard data
