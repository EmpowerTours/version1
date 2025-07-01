from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import sqlite3
import contract  # Import contract.py for transaction functions
import utils     # Import utils.py for Web3 and message parsing

app = FastAPI()

# Mount static files
app.mount("/public", StaticFiles(directory="public"), name="public")

# Wallet connection endpoint
@app.post("/wallet")
async def connect_wallet(data: dict):
    user_id = data.get("telegramUserId")
    wallet_address = data.get("walletAddress")
    if not user_id or not wallet_address:
        raise HTTPException(status_code=400, detail="Missing user_id or wallet_address")
    conn = sqlite3.connect('empowertours.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO sessions (user_id, wallet_address) VALUES (?, ?)", (user_id, wallet_address))
    conn.commit()
    conn.close()
    return {"status": "success"}

# Add other endpoints (e.g., /create_profile, /journal_entry, etc.) from contract.py
@app.post("/create_profile")
async def create_profile(data: dict):
    return await contract.create_profile_tx(data["wallet_address"], data["user_id"])

@app.get("/sessions/{user_id}")
async def get_session(user_id: str):
    conn = sqlite3.connect('empowertours.db')
    cursor = conn.cursor()
    cursor.execute("SELECT wallet_address FROM sessions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return {"wallet_address": result[0] if result else None}

# Add endpoints for journal_entry, add_comment, create_climbing_location, etc.
