
-- Users
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    created_at TEXT
);

-- Goals
CREATE TABLE goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    target TEXT,
    notes TEXT,
    created_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Records (workouts)
CREATE TABLE records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    activity TEXT,
    value REAL,
    created_at TEXT,
    shared TEXT DEFAULT 'none',
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Friends connections (undirected: we insert a single row)
CREATE TABLE friends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    friend_id INTEGER,
    created_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(friend_id) REFERENCES users(id)
);

-- Posts (feed)
CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    content TEXT,
    visibility TEXT CHECK(visibility IN ('friends','community')) DEFAULT 'friends',
    created_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
