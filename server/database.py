import sqlite3
import datetime
import logging
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum

class EventType(Enum):
    INCOMING_SMS = "incoming_sms"
    INCOMING_CALL = "incoming_call"
    OUTGOING_SMS = "outgoing_sms"

class EventStatus(Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    ERROR = "error"

class Database:
    def __init__(self, db_path: str = "smsgate.db") -> None:
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.l = logging.getLogger("Database")
        self._init_db()

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Events table - tracks all system events in an event-sourced manner
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,  -- EventType enum value
                    status TEXT NOT NULL,  -- EventStatus enum value
                    modem_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    body JSON NOT NULL,  -- JSON payload containing event details
                    error TEXT,  -- Optional error message if status is ERROR/FAILED
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Modem state table - tracks current state of modems
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS modem_state (
                    modem_id TEXT PRIMARY KEY,
                    balance REAL,
                    currency TEXT,
                    network TEXT,
                    signal_strength INTEGER,
                    last_balance_check DATETIME,
                    last_network_check DATETIME,
                    last_signal_check DATETIME,
                    is_online BOOLEAN DEFAULT 0,
                    last_online DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Financial activity table - tracks financial events
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS financial_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    modem_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,  -- 'sms_sent', 'ussd_balance_check', etc.
                    amount REAL,
                    currency TEXT,
                    timestamp DATETIME NOT NULL,
                    details TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes for better query performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_modem_id ON events(modem_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_financial_activity_modem_id ON financial_activity(modem_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_financial_activity_timestamp ON financial_activity(timestamp)')

            conn.commit()

    def add_event(self, event_type: EventType, modem_id: str, body: Dict[str, Any], 
                 status: EventStatus = EventStatus.PENDING, error: Optional[str] = None) -> int:
        """Add a new event to the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO events (
                    type, status, modem_id, timestamp, body, error
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                event_type.value,
                status.value,
                modem_id,
                datetime.datetime.now(),
                json.dumps(body),
                error
            ))
            conn.commit()
            return cursor.lastrowid

    def update_event_status(self, event_id: int, status: EventStatus, error: Optional[str] = None) -> None:
        """Update the status of an event."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE events 
                SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status.value, error, event_id))
            conn.commit()

    def get_events(self, modem_id: Optional[str] = None, 
                  event_type: Optional[EventType] = None,
                  status: Optional[EventStatus] = None,
                  limit: int = 100) -> List[Dict[str, Any]]:
        """Get events with optional filtering."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM events WHERE 1=1'
            params = []
            
            if modem_id:
                query += ' AND modem_id = ?'
                params.append(modem_id)
            if event_type:
                query += ' AND type = ?'
                params.append(event_type.value)
            if status:
                query += ' AND status = ?'
                params.append(status.value)
                
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                event = dict(zip(columns, row))
                event['body'] = json.loads(event['body'])
                result.append(event)
            return result

    def update_modem_state(self, modem_id: str, **kwargs) -> None:
        """Update modem state with any provided fields."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if modem exists
            cursor.execute('SELECT 1 FROM modem_state WHERE modem_id = ?', (modem_id,))
            exists = cursor.fetchone() is not None
            
            if not exists:
                # Insert new record
                fields = ['modem_id'] + list(kwargs.keys())
                placeholders = ['?'] * len(fields)
                query = f'''
                    INSERT INTO modem_state ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                '''
                cursor.execute(query, [modem_id] + list(kwargs.values()))
            else:
                # Update existing record
                set_clause = ', '.join(f'{k} = ?' for k in kwargs.keys())
                query = f'''
                    UPDATE modem_state 
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE modem_id = ?
                '''
                cursor.execute(query, list(kwargs.values()) + [modem_id])
            
            conn.commit()

    def get_modem_state(self, modem_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a modem."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM modem_state WHERE modem_id = ?', (modem_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def add_financial_activity(self, modem_id: str, event_type: str, amount: Optional[float] = None,
                             currency: Optional[str] = None, details: Optional[str] = None) -> None:
        """Record a financial activity event."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO financial_activity (
                    modem_id, event_type, amount, currency, timestamp, details
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (modem_id, event_type, amount, currency, datetime.datetime.now(), details))
            conn.commit()

    def get_financial_activity_period(self, modem_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get financial activity for a specific period."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM financial_activity 
                WHERE modem_id = ? 
                AND timestamp >= datetime('now', ?)
                ORDER BY timestamp DESC
            ''', (modem_id, f'-{days} days'))
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()] 