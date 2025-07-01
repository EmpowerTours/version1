import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import sqlite3
import contract
import utils

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    app = FastAPI()
    logger.info("FastAPI app initialized successfully")

    # Mount static files for connect.html
    app.mount("/public", StaticFiles(directory="public"), name="public")
    logger.info("Static files mounted at /public")

    @app.post("/wallet")
    async def connect_wallet(data: dict):
        logger.info(f"Received wallet connection request: {data}")
        user_id = data.get("telegramUserId")
        wallet_address = data.get("walletAddress")
        if not user_id or not wallet_address:
            logger.error("Missing user_id or wallet_address")
            raise HTTPException(status_code=400, detail="Missing user_id or wallet_address")
        conn = sqlite3.connect('empowertours.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO sessions (user_id, wallet_address) VALUES (?, ?)", (user_id, wallet_address))
        conn.commit()
        conn.close()
        logger.info(f"Wallet {wallet_address} connected for user {user_id}")
        return {"status": "success"}

    @app.post("/create_profile")
    async def create_profile(data: dict):
        logger.info(f"Received create_profile request: {data}")
        user = type('User', (), {'id': data['user_id'], 'first_name': 'User', 'username': data.get('username', 'User')})()
        return await contract.create_profile_tx(data["wallet_address"], user)

    @app.get("/sessions/{user_id}")
    async def get_session(user_id: str):
        logger.info(f"Fetching session for user {user_id}")
        conn = sqlite3.connect('empowertours.db')
        cursor = conn.cursor()
        cursor.execute("SELECT wallet_address FROM sessions WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        wallet_address = result[0] if result else None
        logger.info(f"Session for user {user_id}: {wallet_address}")
        return {"wallet_address": wallet_address}

    @app.post("/journal_entry")
    async def journal_entry(data: dict):
        logger.info(f"Received journal_entry request: {data}")
        user = type('User', (), {'id': data['user_id'], 'first_name': 'User', 'username': data.get('username', 'User')})()
        return await contract.add_journal_entry_tx(data["wallet_address"], data["content"], user)

    @app.post("/add_comment")
    async def add_comment(data: dict):
        logger.info(f"Received add_comment request: {data}")
        user = type('User', (), {'id': data['user_id'], 'first_name': 'User', 'username': data.get('username', 'User')})()
        return await contract.add_comment_tx(data["wallet_address"], data["entry_id"], data["content"], user)

    @app.post("/create_climbing_location")
    async def create_climbing_location(data: dict):
        logger.info(f"Received create_climbing_location request: {data}")
        user = type('User', (), {'id': data['user_id'], 'first_name': 'User', 'username': data.get('username', 'User')})()
        return await contract.create_climbing_location_tx(
            data["wallet_address"], data["name"], data["difficulty"], data["latitude"], data["longitude"], data["photo_hash"], user
        )

    @app.post("/purchase_climb")
    async def purchase_climb(data: dict):
        logger.info(f"Received purchase_climb request: {data}")
        user = type('User', (), {'id': data['user_id'], 'first_name': 'User', 'username': data.get('username', 'User')})()
        return await contract.purchase_climbing_location_tx(data["wallet_address"], data["location_id"], user)

    @app.post("/create_tournament")
    async def create_tournament(data: dict):
        logger.info(f"Received create_tournament request: {data}")
        user = type('User', (), {'id': data['user_id'], 'first_name': 'User', 'username': data.get('username', 'User')})()
        return await contract.create_tournament_tx(data["wallet_address"], data["entry_fee"], user)

    @app.post("/join_tournament")
    async def join_tournament(data: dict):
        logger.info(f"Received join_tournament request: {data}")
        user = type('User', (), {'id': data['user_id'], 'first_name': 'User', 'username': data.get('username', 'User')})()
        return await contract.join_tournament_tx(data["wallet_address"], data["tournament_id"], user)

    @app.post("/end_tournament")
    async def end_tournament(data: dict):
        logger.info(f"Received end_tournament request: {data}")
        user = type('User', (), {'id': data['user_id'], 'first_name': 'User', 'username': data.get('username', 'User')})()
        return await contract.end_tournament_tx(data["wallet_address"], data["tournament_id"], data["winner_address"], user)

    @app.get("/climbing_locations")
    async def get_climbing_locations():
        logger.info("Fetching climbing locations")
        locations = await contract.get_climbing_locations()
        logger.info(f"Retrieved {len(locations)} climbing locations")
        return locations

    @app.post("/webhook")
    async def webhook(update: dict):
        logger.info(f"Received webhook update: {update}")
        message, message_type = utils.get_message(update)
        if message:
            logger.info(f"Processed {message_type}: {message}")
        return {"status": "ok"}

except Exception as e:
    logger.error(f"Failed to initialize FastAPI app: {str(e)}")
    raise
