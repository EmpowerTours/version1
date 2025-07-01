from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import sqlite3
import contract
import utils

app = FastAPI()
app.mount("/public", StaticFiles(directory="public"), name="public")

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

@app.post("/create_profile")
async def create_profile(data: dict):
    user = type('User', (), {'id': data['user_id']})()
    return await contract.create_profile_tx(data["wallet_address"], user)

@app.get("/sessions/{user_id}")
async def get_session(user_id: str):
    conn = sqlite3.connect('empowertours.db')
    cursor = conn.cursor()
    cursor.execute("SELECT wallet_address FROM sessions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return {"wallet_address": result[0] if result else None}

@app.post("/journal_entry")
async def journal_entry(data: dict):
    user = type('User', (), {'id': data['user_id']})()
    return await contract.add_journal_entry_tx(data["wallet_address"], data["content"], user)

@app.post("/add_comment")
async def add_comment(data: dict):
    user = type('User', (), {'id': data['user_id']})()
    return await contract.add_comment_tx(data["wallet_address"], data["entry_id"], data["content"], user)

@app.post("/create_climbing_location")
async def create_climbing_location(data: dict):
    user = type('User', (), {'id': data['user_id']})()
    return await contract.create_climbing_location_tx(
        data["wallet_address"], data["name"], data["difficulty"], data["latitude"], data["longitude"], data["photo_hash"], user
    )

@app.post("/purchase_climb")
async def purchase_climb(data: dict):
    user = type('User', (), {'id': data['user_id']})()
    return await contract.purchase_climbing_location_tx(data["wallet_address"], data["location_id"], user)

@app.post("/create_tournament")
async def create_tournament(data: dict):
    user = type('User', (), {'id': data['user_id']})()
    return await contract.create_tournament_tx(data["wallet_address"], data["entry_fee"], user)

@app.post("/join_tournament")
async def join_tournament(data: dict):
    user = type('User', (), {'id': data['user_id']})()
    return await contract.join_tournament_tx(data["wallet_address"], data["tournament_id"], user)

@app.post("/end_tournament")
async def end_tournament(data: dict):
    user = type('User', (), {'id': data['user_id']})()
    return await contract.end_tournament_tx(data["wallet_address"], data["tournament_id"], data["winner_address"], user)

@app.get("/climbing_locations")
async def get_climbing_locations():
    return await contract.get_climbing_locations()

@app.post("/webhook")
async def webhook(update: dict):
    message, message_type = utils.get_message(update)
    if message:
        # Handle Telegram updates if needed
        pass
    return {"status": "ok"}
