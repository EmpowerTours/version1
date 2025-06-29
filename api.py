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

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL))

# Initialize FastAPI and SocketIO
app = FastAPI()
sio = AsyncServer(async_mode='asgi', cors_allowed_origins="*")
app.mount("/socket.io", ASGIApp(sio))

# Initialize SQLite database
conn = sqlite3.connect('empowertours.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        user_id TEXT PRIMARY KEY,
        session_id TEXT,
        wallet_address TEXT
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
        tournament_id INTEGER
    )
''')
conn.commit()

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

@app.post("/connect")
async def connect_wallet(request: ConnectRequest):
    try:
        session_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT OR REPLACE INTO sessions (user_id, session_id, wallet_address) VALUES (?, ?, ?)",
            (request.user_id, session_id, None)
        )
        conn.commit()
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"Error in /connect: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/wallet")
async def set_wallet(request: WalletRequest):
    try:
        cursor.execute(
            "UPDATE sessions SET wallet_address = ? WHERE user_id = ?",
            (request.walletAddress, request.telegramUserId)
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
        await sio.emit('sign_tx', {
            'user_id': request.user_id,
            'tx_data': request.tx_data
        })
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"Error in /sign: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/broadcast")
async def broadcast_transaction_endpoint(request: BroadcastRequest):
    try:
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
        
        if result['status'] == 'success':
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": request.telegramUserId,
                        "text": result['message'],
                        "parse_mode": "HTML"
                    }
                )
                if 'group_message' in result:
                    await session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": CHAT_HANDLE,
                            "text": result['group_message']
                        }
                    )
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
        return {"tx_hash": result.get('tx_hash', ''), "status": result['status']}
    except Exception as e:
        logger.error(f"Error in /broadcast: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
