from fastapi import FastAPI, HTTPException
from socketio import AsyncServer, ASGIApp
from pydantic import BaseModel
import sqlite3
import json
import uuid
import logging
import aiohttp
from web3 import Web3
from dotenv import load_dotenv
import os
from contract import broadcast_transaction
import time  # For expiry

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
TOURS_TOKEN_ADDRESS = os.getenv("TOURS_TOKEN_ADDRESS")
WALLET_CONNECT_PROJECT_ID = os.getenv("WALLET_CONNECT_PROJECT_ID")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_HANDLE = "@empowertourschat"
EXPIRY_SECONDS = 1800  # 30 minutes

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL))

# Initialize FastAPI and SocketIO
app = FastAPI()
sio = AsyncServer(async_mode='asgi', cors_allowed_origins="*")
app.mount("/socket.io", ASGIApp(sio))

# Initialize SQLite database
conn = sqlite3.connect('empowertours.db')
cursor = conn.cursor()

# Existing tables
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        user_id TEXT PRIMARY KEY,
        session_id TEXT,
        wallet_address TEXT,
        connected_at INTEGER  -- Timestamp for expiry
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS pending_txs (
        user_id TEXT,
        tx_type TEXT,
        tx_data TEXT,
        name TEXT,
        difficulty TEXT,
        latitude INTEGER,
        longitude INTEGER,
        photo_hash TEXT,
        location_id INTEGER,
        tournament_id INTEGER,
        UNIQUE(user_id, tx_type)  -- Prevent duplicates
    )
''')

# New tables for features
cursor.execute('''
    CREATE TABLE IF NOT EXISTS climbs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_user_id TEXT,
        title TEXT,
        description TEXT,
        picture_url TEXT,  -- Encrypted
        location TEXT,     -- Encrypted (JSON: {'lat': float, 'lon': float})
        price_tours INTEGER,
        created_at INTEGER
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        climb_id INTEGER,
        buyer_user_id TEXT,
        purchased_at INTEGER
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS journals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        climb_id INTEGER,
        user_id TEXT,
        entry_text TEXT,
        date INTEGER
    )
''')
conn.commit()

# Simple encryption (XOR with key; replace with better e.g., cryptography.fernet)
ENCRYPT_KEY = b'secret_key'  # Use env var in prod
def encrypt(data: str) -> str:
    return ''.join(chr(ord(c) ^ ENCRYPT_KEY[i % len(ENCRYPT_KEY)]) for i, c in enumerate(data))

def decrypt(data: str) -> str:
    return encrypt(data)  # XOR is symmetric

class ConnectRequest(BaseModel):
    user_id: str

class WalletRequest(BaseModel):
    telegramUserId: str
    walletAddress: str

class SignRequest(BaseModel):
    user_id: str
    tx_data: dict

class BroadcastRequest(BaseModel):
    telegramUserId: str
    signedTxHex: str

class HashRequest(BaseModel):  # New for automated submission
    telegramUserId: str
    txHash: str

class BuildClimbRequest(BaseModel):
    user_id: str
    title: str
    description: str
    picture_url: str
    location: dict  # {'lat': float, 'lon': float}
    price_tours: int

class PurchaseClimbRequest(BaseModel):
    user_id: str
    climb_id: int

class JournalRequest(BaseModel):
    user_id: str
    climb_id: int
    entry_text: str

@app.post("/connect")
async def connect_wallet(request: ConnectRequest):
    try:
        session_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT OR REPLACE INTO sessions (user_id, session_id, wallet_address, connected_at) VALUES (?, ?, ?, ?)",
            (request.user_id, session_id, None, int(time.time()))
        )
        conn.commit()
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"Error in /connect: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/wallet")
async def set_wallet(request: WalletRequest):
    try:
        # Check if already connected and not expired
        cursor.execute("SELECT connected_at FROM sessions WHERE user_id = ?", (request.telegramUserId,))
        row = cursor.fetchone()
        if row and time.time() - row[0] < EXPIRY_SECONDS:
            return {"status": "already_connected"}

        cursor.execute(
            "UPDATE sessions SET wallet_address = ?, connected_at = ? WHERE user_id = ?",
            (request.walletAddress, int(time.time()), request.telegramUserId)
        )
        conn.commit()
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": request.telegramUserId,
                    "text": f"Wallet connected: {request.walletAddress}! 🎉 Use /createprofile to join.",
                    "parse_mode": "HTML"
                }
            )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in /wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sign")
async def sign_transaction(request: SignRequest):
    try:
        # Prevent double: Check pending
        cursor.execute("SELECT 1 FROM pending_txs WHERE user_id = ?", (request.user_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Transaction already pending")

        # Insert pending (assuming tx_data includes all fields)
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data) VALUES (?, ?, ?)",
            (request.user_id, 'transfer', json.dumps(request.tx_data))  # Simplify; add fields as needed
        )
        conn.commit()

        await sio.emit('sign_tx', {
            'user_id': request.user_id,
            'tx_data': request.tx_data
        })
        return {"status": "sent"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Duplicate transaction type pending")
    except Exception as e:
        logger.error(f"Error in /sign: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/broadcast")
async def broadcast_transaction_endpoint(request: BroadcastRequest):
    try:
        # Check connection expiry
        cursor.execute("SELECT connected_at FROM sessions WHERE user_id = ?", (request.telegramUserId,))
        row = cursor.fetchone()
        if not row or time.time() - row[0] > EXPIRY_SECONDS:
            raise HTTPException(status_code=401, detail="Session expired; reconnect wallet")

        cursor.execute(
            "SELECT tx_type, name, difficulty, location_id, tournament_id FROM pending_txs WHERE user_id = ? ORDER BY ROWID DESC LIMIT 1",
            (request.telegramUserId,)
        )
        pending_tx = cursor.fetchone()
        if not pending_tx:
            raise HTTPException(status_code=404, detail="No pending transaction found")
        
        tx_type, name, difficulty, location_id, tournament_id = pending_tx
        result = await broadcast_transaction(
            signed_tx_hex=request.signedTxHex,
            pending_tx={
                'tx_type': tx_type,
                'wallet_address': cursor.execute("SELECT wallet_address FROM sessions WHERE user_id = ?", (request.telegramUserId,)).fetchone()[0],
                'name': name,
                'difficulty': difficulty,
                'location_id': location_id,
                'tournament_id': tournament_id
            },
            user={'id': request.telegramUserId, 'first_name': 'User', 'username': f"user_{request.telegramUserId}"},
            context=None
        )
        
        tx_hash = result.get('tx_hash', '')
        explorer_url = f"https://monadscan.com/tx/{tx_hash}"
        
        if result['status'] == 'success':
            async with aiohttp.ClientSession() as session:
                user_msg = f"Transaction confirmed! <a href='{explorer_url}'>Tx: {tx_hash}</a> 🪙 Action completed."
                user_resp = await session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": request.telegramUserId,
                        "text": user_msg,
                        "parse_mode": "HTML"
                    }
                )
                if 'group_message' in result:
                    group_msg = f"New activity by {result.get('username', 'user')} on EmpowerTours! 🧗 <a href='{explorer_url}'>Tx: {tx_hash}</a>"
                    group_resp = await session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": CHAT_HANDLE,
                            "text": group_msg,
                            "parse_mode": "HTML"
                        }
                    )
                    if not group_resp.json().get('ok'):
                        logger.error(f"Group notification failed: {group_resp.json()['description']}")
        else:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": request.telegramUserId,
                        "text": result['message'],
                        "parse_mode": "HTML"
                    }
                )
        return {"tx_hash": tx_hash, "status": result['status']}
    except Exception as e:
        logger.error(f"Error in /broadcast: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit_hash")  # New: For automated frontend submission
async def submit_tx_hash(request: HashRequest):
    try:
        # Check expiry as above
        cursor.execute("SELECT connected_at FROM sessions WHERE user_id = ?", (request.telegramUserId,))
        row = cursor.fetchone()
        if not row or time.time() - row[0] > EXPIRY_SECONDS:
            raise HTTPException(status_code=401, detail="Session expired; reconnect wallet")

        # Confirm tx
        receipt = w3.eth.wait_for_transaction_receipt(request.txHash, timeout=120)
        if receipt.status != 1:
            raise HTTPException(status_code=400, detail="Transaction failed")

        # Clear pending
        cursor.execute("DELETE FROM pending_txs WHERE user_id = ?", (request.telegramUserId,))
        conn.commit()

        explorer_url = f"https://monadscan.com/tx/{request.txHash}"
        async with aiohttp.ClientSession() as session:
            user_msg = f"Transaction confirmed automatically! <a href='{explorer_url}'>Tx: {request.txHash}</a> 🪙 Action completed."
            await session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": request.telegramUserId,
                    "text": user_msg,
                    "parse_mode": "HTML"
                }
            )
            # Group notification similar to above
            group_msg = f"New activity on EmpowerTours! 🧗 <a href='{explorer_url}'>Tx: {request.txHash}</a>"
            group_resp = await session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_HANDLE,
                    "text": group_msg,
                    "parse_mode": "HTML"
                }
            )
            if not group_resp.json().get('ok'):
                logger.error(f"Group notification failed: {group_resp.json()['description']}")
        return {"status": "success", "tx_hash": request.txHash}
    except Exception as e:
        logger.error(f"Error in /submit_hash: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# New endpoints for features

@app.post("/build_climb")
async def build_climb(request: BuildClimbRequest):
    try:
        enc_picture = encrypt(request.picture_url)
        enc_location = encrypt(json.dumps(request.location))
        cursor.execute(
            "INSERT INTO climbs (creator_user_id, title, description, picture_url, location, price_tours, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (request.user_id, request.title, request.description, enc_picture, enc_location, request.price_tours, int(time.time()))
        )
        conn.commit()
        return {"status": "success", "climb_id": cursor.lastrowid}
    except Exception as e:
        logger.error(f"Error in /build_climb: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/find_climbs")
async def find_climbs():
    try:
        cursor.execute("SELECT id, title, description, price_tours FROM climbs")
        climbs = [{"id": row[0], "title": row[1], "desc": row[2], "price": row[3]} for row in cursor.fetchall()]
        return {"climbs": climbs}
    except Exception as e:
        logger.error(f"Error in /find_climbs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/purchase_climb")
async def purchase_climb(request: PurchaseClimbRequest):
    try:
        # Fetch climb
        cursor.execute("SELECT creator_user_id, price_tours FROM climbs WHERE id = ?", (request.climb_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Climb not found")
        creator_id, price = row

        # Build transfer tx to creator (similar to sendTours)
        creator_wallet = cursor.execute("SELECT wallet_address FROM sessions WHERE user_id = ?", (creator_id,)).fetchone()[0]
        tx_data = {
            "value": 0,
            "chainId": 143,
            "from": cursor.execute("SELECT wallet_address FROM sessions WHERE user_id = ?", (request.user_id,)).fetchone()[0],
            "to": TOURS_TOKEN_ADDRESS,
            "data": w3.eth.contract(address=TOURS_TOKEN_ADDRESS).functions.transfer(creator_wallet, price * 10**18).build_transaction()['data']  # Assume 18 decimals
        }

        # Insert pending purchase tx
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data) VALUES (?, ?, ?)",
            (request.user_id, 'purchase_climb', json.dumps(tx_data))
        )
        conn.commit()

        return {"status": "tx_built", "tx_data": tx_data}  # Frontend signs/broadcasts
    except Exception as e:
        logger.error(f"Error in /purchase_climb: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_journal")
async def add_journal(request: JournalRequest):
    try:
        # Check purchase
        cursor.execute("SELECT 1 FROM purchases WHERE climb_id = ? AND buyer_user_id = ?", (request.climb_id, request.user_id))
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Not purchased")

        cursor.execute(
            "INSERT INTO journals (climb_id, user_id, entry_text, date) VALUES (?, ?, ?, ?)",
            (request.climb_id, request.user_id, request.entry_text, int(time.time()))
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in /add_journal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_climb/{climb_id}")
async def get_climb(climb_id: int, user_id: str):
    try:
        # Check purchase for full details
        cursor.execute("SELECT 1 FROM purchases WHERE climb_id = ? AND buyer_user_id = ?", (climb_id, user_id))
        purchased = bool(cursor.fetchone())

        cursor.execute("SELECT title, description, picture_url, location FROM climbs WHERE id = ?", (climb_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Climb not found")

        data = {"title": row[0], "desc": row[1]}
        if purchased:
            data["picture_url"] = decrypt(row[2])
            data["location"] = json.loads(decrypt(row[3]))

        return data
    except Exception as e:
        logger.error(f"Error in /get_climb: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
