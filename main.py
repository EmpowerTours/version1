import logging
import os
import signal
import asyncio
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, FileResponse
from contextlib import asynccontextmanager
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import aiohttp
from web3 import AsyncWeb3
from web3.providers.async_rpc import AsyncHTTPProvider
from dotenv import load_dotenv
import html
import uvicorn
import socket
import json
import subprocess
from datetime import datetime
from tenacity import retry, wait_exponential, stop_after_attempt  # Added for retries

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Global variables
application = None
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")
CHAT_HANDLE = os.getenv("CHAT_HANDLE")
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL")
TOURS_TOKEN_ADDRESS = os.getenv("TOURS_TOKEN_ADDRESS")
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS")
WALLET_CONNECT_PROJECT_ID = os.getenv("WALLET_CONNECT_PROJECT_ID")
ENVIO_GRAPHQL_URL = os.getenv("ENVIO_GRAPHQL_URL")
EXPLORER_URL = "https://monadscan.com"
WMON_ADDRESS = os.getenv("WMON_ADDRESS")
CLIMBING_V2_ADDRESS = os.getenv("CLIMBING_V2_ADDRESS")

# In-memory session storage (wallet connections are ephemeral)
sessions = {}           # user_id -> {"wallet_address": str}
reverse_sessions = {}   # wallet_address -> user_id
pending_wallets = {}    # user_id -> pending wallet data
journal_data = {}       # user_id -> pending journal data

# Log environment variables
logger.info("Environment variables:")
logger.info(f"TELEGRAM_TOKEN: {'Set' if TELEGRAM_TOKEN else 'Missing'}")
logger.info(f"API_BASE_URL: {'Set' if API_BASE_URL else 'Missing'}")
logger.info(f"CHAT_HANDLE: {'Set' if CHAT_HANDLE else 'Missing'}")
logger.info(f"MONAD_RPC_URL: {'Set' if MONAD_RPC_URL else 'Missing'}")
logger.info(f"TOURS_TOKEN_ADDRESS: {'Set' if TOURS_TOKEN_ADDRESS else 'Missing'}")
logger.info(f"OWNER_ADDRESS: {'Set' if OWNER_ADDRESS else 'Missing'}")
logger.info(f"WALLET_CONNECT_PROJECT_ID: {'Set' if WALLET_CONNECT_PROJECT_ID else 'Missing'}")
logger.info(f"ENVIO_GRAPHQL_URL: {ENVIO_GRAPHQL_URL or 'Missing'}")
logger.info(f"WMON_ADDRESS: {'Set' if WMON_ADDRESS else 'Missing'}")
logger.info(f"CLIMBING_V2_ADDRESS: {'Set' if CLIMBING_V2_ADDRESS else 'Missing'}")
missing_vars = []
if not TELEGRAM_TOKEN: missing_vars.append("TELEGRAM_TOKEN")
if not API_BASE_URL: missing_vars.append("API_BASE_URL")
if not CHAT_HANDLE: missing_vars.append("CHAT_HANDLE")
if not MONAD_RPC_URL: missing_vars.append("MONAD_RPC_URL")
if not TOURS_TOKEN_ADDRESS: missing_vars.append("TOURS_TOKEN_ADDRESS")
if not OWNER_ADDRESS: missing_vars.append("OWNER_ADDRESS")
if not WALLET_CONNECT_PROJECT_ID: missing_vars.append("WALLET_CONNECT_PROJECT_ID")
if not ENVIO_GRAPHQL_URL: missing_vars.append("ENVIO_GRAPHQL_URL")
if not WMON_ADDRESS: missing_vars.append("WMON_ADDRESS")
if not CLIMBING_V2_ADDRESS: missing_vars.append("CLIMBING_V2_ADDRESS")
if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
    logger.warning("Proceeding with limited functionality")
else:
    logger.info("All required environment variables are set")

# Envio GraphQL query helper
async def query_envio(query: str, variables: dict = None) -> dict:
    """Query Envio GraphQL endpoint for blockchain data"""
    if not ENVIO_GRAPHQL_URL:
        logger.error("ENVIO_GRAPHQL_URL not set")
        return None
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            async with session.post(ENVIO_GRAPHQL_URL, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.error(f"Envio query failed: {resp.status}")
                return None
    except Exception as e:
        logger.error(f"Envio query error: {e}")
        return None

async def get_user_purchases(wallet_address: str) -> list:
    """Get all climb purchases for a wallet from Envio"""
    query = """
    query GetUserPurchases($holder: String!) {
        ClimbAccessBadge(where: {holder: {_eq: $holder}}) {
            tokenId
            locationId
            holder
            holderTelegramId
            purchasedAt
        }
    }
    """
    result = await query_envio(query, {"holder": wallet_address.lower()})
    if result and "data" in result:
        return result["data"].get("ClimbAccessBadge", [])
    return []

async def has_purchased_climb(wallet_address: str, location_id: int) -> bool:
    """Check if wallet has purchased a specific climb"""
    purchases = await get_user_purchases(wallet_address)
    return any(p.get("locationId") == str(location_id) for p in purchases)

async def get_user_climb_proofs(wallet_address: str) -> list:
    """Get all climb proofs (journal NFTs) for a wallet from Envio"""
    query = """
    query GetUserClimbProofs($holder: String!) {
        ClimbProofNFT(where: {holder: {_eq: $holder}}) {
            tokenId
            locationId
            holder
            holderTelegramId
            photoHash
            toursRewarded
            mintedAt
        }
    }
    """
    result = await query_envio(query, {"holder": wallet_address.lower()})
    if result and "data" in result:
        return result["data"].get("ClimbProofNFT", [])
    return []

async def get_nft_by_id(token_id: int) -> dict:
    """Get NFT details by token ID from Envio"""
    # Access Badges are 1-999,999, Climb Proofs are 1,000,000+
    if token_id < 1000000:
        query = """
        query GetAccessBadge($tokenId: String!) {
            ClimbAccessBadge(where: {tokenId: {_eq: $tokenId}}) {
                tokenId
                locationId
                holder
                holderTelegramId
                purchasedAt
            }
        }
        """
        result = await query_envio(query, {"tokenId": str(token_id)})
        if result and "data" in result:
            badges = result["data"].get("ClimbAccessBadge", [])
            if badges:
                badge = badges[0]
                badge["nftType"] = "Access Badge"
                return badge
    else:
        query = """
        query GetClimbProof($tokenId: String!) {
            ClimbProofNFT(where: {tokenId: {_eq: $tokenId}}) {
                tokenId
                locationId
                holder
                holderTelegramId
                photoHash
                toursRewarded
                mintedAt
            }
        }
        """
        result = await query_envio(query, {"tokenId": str(token_id)})
        if result and "data" in result:
            proofs = result["data"].get("ClimbProofNFT", [])
            if proofs:
                proof = proofs[0]
                proof["nftType"] = "Climb Proof"
                return proof
    return None

TOURS_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

WMON_ABI = [
    {
        "name": "deposit",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [],
        "outputs": []
    },
    {
        "name": "withdraw",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "amount", "type": "uint256"}],
        "outputs": []
    },
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}]
    },
    {
        "name": "approve",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "outputs": [{"name": "", "type": "bool"}]
    },
    {
        "name": "allowance",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "outputs": [{"name": "", "type": "uint256"}]
    }
]

CLIMBING_V2_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "creatorFid", "type": "uint256"},
            {"internalType": "uint256", "name": "creatorTelegramId", "type": "uint256"},
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "difficulty", "type": "string"},
            {"internalType": "int256", "name": "latitude", "type": "int256"},
            {"internalType": "int256", "name": "longitude", "type": "int256"},
            {"internalType": "string", "name": "photoProofIPFS", "type": "string"},
            {"internalType": "string", "name": "description", "type": "string"},
            {"internalType": "uint256", "name": "priceWmon", "type": "uint256"}
        ],
        "name": "createLocation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"internalType": "uint256", "name": "buyerFid", "type": "uint256"},
            {"internalType": "uint256", "name": "buyerTelegramId", "type": "uint256"}
        ],
        "name": "purchaseLocation",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"internalType": "uint256", "name": "authorFid", "type": "uint256"},
            {"internalType": "uint256", "name": "authorTelegramId", "type": "uint256"},
            {"internalType": "string", "name": "entryText", "type": "string"},
            {"internalType": "string", "name": "photoIPFS", "type": "string"}
        ],
        "name": "addJournalEntry",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "locations",
        "outputs": [
            {"internalType": "uint256", "name": "id", "type": "uint256"},
            {"internalType": "address", "name": "creator", "type": "address"},
            {"internalType": "uint256", "name": "creatorFid", "type": "uint256"},
            {"internalType": "uint256", "name": "creatorTelegramId", "type": "uint256"},
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "difficulty", "type": "string"},
            {"internalType": "int256", "name": "latitude", "type": "int256"},
            {"internalType": "int256", "name": "longitude", "type": "int256"},
            {"internalType": "string", "name": "photoProofIPFS", "type": "string"},
            {"internalType": "string", "name": "description", "type": "string"},
            {"internalType": "uint256", "name": "priceWmon", "type": "uint256"},
            {"internalType": "bool", "name": "isActive", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "name": "hasPurchased",
        "outputs": [
            {"internalType": "bool", "name": "", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "name": "lastJournalTime",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "locationCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "locationCreationFee",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "creator", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "creatorFid", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "creatorTelegramId", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "name", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "difficulty", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "priceWmon", "type": "uint256"}
        ],
        "name": "LocationCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"indexed": True, "internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "buyer", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "buyerFid", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "buyerTelegramId", "type": "uint256"}
        ],
        "name": "AccessBadgeMinted",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"indexed": True, "internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "author", "type": "address"},
            {"indexed": False, "internalType": "string", "name": "photoIPFS", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "toursRewarded", "type": "uint256"}
        ],
        "name": "ClimbProofMinted",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "locationId", "type": "uint256"}
        ],
        "name": "LocationDisabled",
        "type": "event"
    }
]

# Global blockchain variables
w3 = None
contract = None
tours_contract = None
wmon_contract = None
webhook_failed = False
processed_updates = set()  # To prevent duplicate processing
climb_cache = None  # Cache for climbs
cache_timestamp = 0
CACHE_TTL = 300  # 5 minutes

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
async def initialize_web3():
    global w3, contract, tours_contract, wmon_contract
    if not MONAD_RPC_URL or not CLIMBING_V2_ADDRESS or not TOURS_TOKEN_ADDRESS or not WMON_ADDRESS:
        logger.error("Cannot initialize Web3: missing blockchain-related environment variables")
        return False
    try:
        w3 = AsyncWeb3(AsyncHTTPProvider(MONAD_RPC_URL))
        is_connected = await w3.is_connected()
        if is_connected:
            logger.info("AsyncWeb3 initialized successfully")
            contract = w3.eth.contract(address=w3.to_checksum_address(CLIMBING_V2_ADDRESS), abi=CLIMBING_V2_ABI)
            tours_contract = w3.eth.contract(address=w3.to_checksum_address(TOURS_TOKEN_ADDRESS), abi=TOURS_ABI)
            wmon_contract = w3.eth.contract(address=w3.to_checksum_address(WMON_ADDRESS), abi=WMON_ABI)
            logger.info("Contracts initialized successfully (ClimbingLocationsV2)")
            return True
        else:
            raise Exception("Web3 not connected")
    except Exception as e:
        logger.error(f"Error initializing Web3: {str(e)}")
        raise

def escape_html(text):
    if not text:
        return ""
    return html.escape(str(text))

async def send_notification(chat_id, message):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        try:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            async with session.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json=payload
            ) as response:
                response_data = await response.json()
                logger.info(f"Sent notification to chat {chat_id}: payload={json.dumps(payload, default=str)}, response={response_data}")
                if response_data.get("ok"):
                    return response_data
                else:
                    logger.error(f"Failed to send notification to chat {chat_id}: {response_data}")
                    return response_data
        except Exception as e:
            logger.error(f"Error in send_notification to chat {chat_id}: {str(e)}")
            return {"ok": False, "error": str(e)}

async def check_webhook():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        try:
            async with session.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo") as response:
                status = response.status
                data = await response.json()
                logger.info(f"Webhook info: status={status}, response={data}")
                return data.get("ok") and data.get("result", {}).get("url") == f"{API_BASE_URL.rstrip('/')}/webhook"
        except Exception as e:
            logger.error(f"Error checking webhook: {str(e)}")
            return False

async def reset_webhook():
    await asyncio.sleep(0.5)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        retries = 5
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"Webhook reset attempt {attempt}/{retries}")
                async with session.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook",
                    json={"drop_pending_updates": True}
                ) as response:
                    status = response.status
                    delete_data = await response.json()
                    logger.info(f"Webhook cleared: status={status}, response={delete_data}")
                    if not delete_data.get("ok"):
                        logger.error(f"Failed to delete webhook: status={status}, response={delete_data}")
                        continue
                webhook_url = f"{API_BASE_URL.rstrip('/')}/webhook"
                logger.info(f"Setting webhook to {webhook_url}")
                async with session.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                    json={"url": webhook_url, "max_connections": 100, "drop_pending_updates": True}
                ) as response:
                    status = response.status
                    set_data = await response.json()
                    logger.info(f"Webhook set: status={status}, response={set_data}")
                    if set_data.get("ok"):
                        logger.info("Verifying webhook after setting")
                        webhook_ok = await check_webhook()
                        if webhook_ok:
                            logger.info("Webhook verified successfully")
                            return True
                        else:
                            logger.error("Webhook verification failed after setting")
                    if set_data.get("error_code") == 429:
                        retry_after = set_data.get("parameters", {}).get("retry_after", 1)
                        logger.warning(f"Rate limited by Telegram, retrying after {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    logger.error(f"Failed to set webhook: status={status}, response={set_data}")
            except Exception as e:
                logger.error(f"Error resetting webhook on attempt {attempt}/{retries}: {str(e)}")
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
        logger.error("All webhook reset attempts failed. Forcing polling mode.")
        global webhook_failed
        webhook_failed = True
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /start command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        welcome_message = (
            f"Welcome to EmpowerTours! 🧗\n\n"
            f"Discover and share climbing locations on Monad.\n\n"
            f"<b>Get Started:</b>\n"
            f"1. /connectwallet - Link your wallet\n"
            f"2. /findaclimb - Browse climbs\n"
            f"3. /buildaclimb - Create your own (35 WMON)\n\n"
            f"Run /tutorial for a full guide or /help for commands.\n"
            f"Join us: <a href=\"https://t.me/empowertourschat\">EmpowerTours Chat</a>"
        )
        await update.message.reply_text(welcome_message, parse_mode="HTML")
        logger.info(f"Sent /start response to user {update.effective_user.id}: {welcome_message}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /start for user {update.effective_user.id}: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /ping command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        webhook_ok = await check_webhook()
        status = "Webhook OK" if webhook_ok else "Webhook failed, using polling"
        await update.message.reply_text(f"Pong! Bot is running. {status}. Try /start or /buildaclimb.")
        logger.info(f"Sent /ping response to user {update.effective_user.id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /ping: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def clearcache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /clearcache command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        await update.message.reply_text("Clearing cache with dummy messages to reset Telegram responses.")
        await send_notification(update.effective_chat.id, "Dummy message 1 to clear Telegram cache.")
        if CHAT_HANDLE:
            await send_notification(CHAT_HANDLE, "Dummy message 2 to clear Telegram cache.")
        await reset_webhook()
        await update.message.reply_text("Cache cleared. Try /start again.")
        logger.info(f"Sent /clearcache response to user {update.effective_user.id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /clearcache: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def forcewebhook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /forcewebhook command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        await update.message.reply_text("Attempting to force reset webhook...")
        webhook_success = await reset_webhook()
        if webhook_success:
            await update.message.reply_text("Webhook reset successful!")
        else:
            await update.message.reply_text("Webhook reset failed. Falling back to polling. Check logs for details.")
        logger.info(f"Sent /forcewebhook response to user {update.effective_user.id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /forcewebhook: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    command_text = update.message.text if update.message else "Unknown command"
    logger.info(f"Received command: {command_text} from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        webhook_ok = await check_webhook()
        if webhook_ok:
            await update.effective_message.reply_text("Webhook is correctly set to https://version1-production.up.railway.app/webhook")
        else:
            await update.effective_message.reply_text("Webhook is not correctly set. Use /forcewebhook to reset or check logs.")
        logger.info(f"Sent /debug response to user {update.effective_user.id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /debug: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.effective_message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /tutorial command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        if not CHAT_HANDLE or not MONAD_RPC_URL:
            logger.error("CHAT_HANDLE or MONAD_RPC_URL missing, /tutorial command limited")
            await update.message.reply_text("Tutorial unavailable due to missing configuration (CHAT_HANDLE or MONAD_RPC_URL). Try /help! 😅")
            logger.info(f"/tutorial failed due to missing config, took {time.time() - start_time:.2f} seconds")
            return
        tutorial_text = (
            "<b>EmpowerTours Tutorial</b>\n\n"
            "<b>1. Setup Your Wallet</b>\n"
            "• Install MetaMask on your phone or browser\n"
            "• Add Monad mainnet (Chain ID: 143)\n"
            "• Get $MON from a DEX or bridge\n"
            "• Wrap some MON to WMON for transactions\n\n"
            "<b>2. Connect to EmpowerTours</b>\n"
            "• Use /connectwallet to link your wallet\n"
            "• Mobile: Opens MetaMask directly\n"
            "• Desktop: Opens browser to connect\n\n"
            "<b>3. Create Climbing Locations</b>\n"
            "• /buildaclimb [name] [difficulty] - Create a climb (35 WMON)\n"
            "• Add photos and GPS coordinates when prompted\n"
            "• Set your own purchase price for others\n\n"
            "<b>4. Explore &amp; Purchase</b>\n"
            "• /findaclimb - Browse available climbs\n"
            "• /viewclimb [id] - View climb details\n"
            "• /purchaseclimb [id] - Buy access to a climb (price set by creator)\n"
            "• /mypurchases - View your purchased climbs\n\n"
            "<b>5. Check Status</b>\n"
            "• /balance - Check your $MON and WMON balance\n"
            "• /help - List all commands\n\n"
            "Join our community: <a href=\"https://t.me/empowertourschat\">EmpowerTours Chat</a>"
        )
        await update.message.reply_text(tutorial_text, parse_mode="HTML")
        logger.info(f"Sent /tutorial response to user {update.effective_user.id}: {tutorial_text}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /tutorial for user {update.effective_user.id}: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error in tutorial: {error_msg}. Try again or use /help! 😅 Contact support at {support_link}.", parse_mode="HTML")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /help command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        help_text = (
            "<b>EmpowerTours Commands</b>\n\n"
            "<b>Getting Started</b>\n"
            "/start - Welcome message\n"
            "/tutorial - Setup guide\n"
            "/connectwallet - Connect wallet (Monad Chain ID 143)\n\n"
            "<b>Climbing Locations</b>\n"
            "/buildaclimb [name] [difficulty] - Create a climb (35 WMON)\n"
            "/findaclimb - Browse available climbs\n"
            "/viewclimb [id] - View climb details\n"
            "/purchaseclimb [id] - Buy access (price set by creator)\n"
            "/mypurchases - View your purchased climbs\n\n"
            "<b>Journal &amp; NFTs</b>\n"
            "/journal [location_id] - Log a climb (earn NFT + TOURS)\n"
            "/mynfts - View your NFTs\n"
            "/viewnft [id] - View NFT details\n\n"
            "<b>Wallet</b>\n"
            "/balance - Check MON, WMON, TOURS balance\n"
            "/wrapmon [amount] - Convert MON to WMON\n"
            "/unwrapmon [amount] - Convert WMON to MON\n\n"
            "<b>Utilities</b>\n"
            "/ping - Check bot status\n\n"
            "Need help? <a href=\"https://t.me/empowertourschat\">EmpowerTours Chat</a>"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")
        logger.info(f"Sent /help response to user {update.effective_user.id}: {help_text}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /help: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def connect_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /connectwallet command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /connectwallet command disabled")
        await update.message.reply_text("Wallet connection unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/connectwallet failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        base_url = API_BASE_URL.rstrip('/')
        connect_url = f"{base_url}/public/connect.html?userId={user_id}"
        # Create MetaMask deeplink for mobile - strips https:// for the deeplink format
        connect_url_for_deeplink = connect_url.replace('https://', '').replace('http://', '')
        metamask_deeplink = f"https://metamask.app.link/dapp/{connect_url_for_deeplink}"
        logger.info(f"Generated connect URL: {connect_url}, MetaMask deeplink: {metamask_deeplink}")
        # Provide both mobile deeplink and desktop browser link
        keyboard = [
            [InlineKeyboardButton("📱 Open in MetaMask (Mobile)", url=metamask_deeplink)],
            [InlineKeyboardButton("🖥️ Open in Browser (Desktop)", url=connect_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            "<b>Connect Your Wallet</b>\n\n"
            "📱 <b>Mobile:</b> Tap 'Open in MetaMask' - this will launch MetaMask directly.\n\n"
            "🖥️ <b>Desktop:</b> Tap 'Open in Browser' and connect via MetaMask extension.\n\n"
            "After connecting, use /balance to check your status or /buildaclimb to create a climb. "
            "Need help? <a href=\"https://t.me/empowertourschat\">EmpowerTours Chat</a>"
        )
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="HTML")
        logger.info(f"Sent /connectwallet response to user {update.effective_user.id}, took {time.time() - start_time:.2f} seconds")
        await set_pending_wallet(user_id, {"awaiting_wallet": True, "timestamp": time.time()})
        logger.info(f"Added user {user_id} to pending_wallets: {pending_wallets.get(user_id)}")
    except Exception as e:
        logger.error(f"Error in /connectwallet for user {user_id}: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def handle_wallet_address(user_id: str, wallet_address: str, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    logger.info(f"Handling wallet address for user {user_id}: {wallet_address}")
    pending = await get_pending_wallet(user_id)
    if not pending or not pending.get("awaiting_wallet"):
        logger.warning(f"No pending wallet connection for user {user_id}")
        logger.info(f"/handle_wallet_address no pending connection, took {time.time() - start_time:.2f} seconds")
        return
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, wallet connection disabled")
        await context.bot.send_message(user_id, "Wallet connection unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/handle_wallet_address failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    try:
        if w3 and w3.is_address(wallet_address):
            checksum_address = w3.to_checksum_address(wallet_address)
            await set_session(user_id, checksum_address)
            await context.bot.send_message(user_id, f"Wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address}) connected! Try /buildaclimb or /balance. 🪙", parse_mode="Markdown")
            await delete_pending_wallet(user_id)
            logger.info(f"Wallet connected for user {user_id}: {checksum_address}, took {time.time() - start_time:.2f} seconds")
        else:
            await context.bot.send_message(user_id, "Invalid wallet address or blockchain unavailable. Try /connectwallet again.")
            logger.info(f"/handle_wallet_address failed due to invalid address or blockchain, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in handle_wallet_address: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await context.bot.send_message(user_id, f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def journal_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log a climb to earn a Climb Proof NFT and TOURS tokens - /journal [location_id]"""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received /journal command from user {user_id}")
    try:
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("No wallet connected. Use /connectwallet first!")
            return

        if not w3 or not contract:
            await update.message.reply_text("Blockchain connection unavailable. Try again later!")
            return

        checksum_address = w3.to_checksum_address(wallet_address)

        # Check if user has any purchased climbs
        purchases = await get_user_purchases(checksum_address)
        if not purchases:
            await update.message.reply_text(
                "You need to purchase a climbing location first!\n\n"
                "Use /findaclimb to browse available climbs, then /purchaseclimb [id] to buy access."
            )
            return

        # Check if location_id was provided
        if not context.args or len(context.args) < 1:
            # Show purchased locations
            message = "Usage: /journal [location_id]\n\nYour purchased climbs:\n"
            for purchase in purchases[:10]:
                loc_id = purchase.get("locationId", "?")
                message += f"  - Location #{loc_id}\n"
            message += "\nSelect a location ID and send the photo of your climb."
            await update.message.reply_text(message)
            return

        try:
            location_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid location ID. Please enter a number.")
            return

        # Check if user has purchased this specific location
        has_access = any(p.get("locationId") == str(location_id) for p in purchases)
        if not has_access:
            await update.message.reply_text(
                f"You don't have access to location #{location_id}.\n"
                f"Use /purchaseclimb {location_id} first to buy access."
            )
            return

        await update.message.reply_text(
            f"Logging climb for Location #{location_id}!\n\n"
            f"Please send a photo of your climb. This will mint a Climb Proof NFT "
            f"and reward you 1-10 TOURS tokens!"
        )
        await set_journal_data(user_id, {
            "location_id": location_id,
            "awaiting_photo": True,
            "timestamp": time.time()
        })
        logger.info(f"/journal initiated for user {user_id}, location {location_id}, awaiting photo, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /journal: {str(e)}")
        error_msg = html.escape(str(e))
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support.", parse_mode="HTML")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received photo from user {user_id} in chat {update.effective_chat.id}")
    if not w3 or not contract:
        logger.error("Web3 not initialized, photo handling disabled")
        await update.message.reply_text("Photo processing unavailable due to blockchain issues. Try again later!")
        return
    try:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        # Hash the file_id to fixed 32-byte hex (reduces gas/storage)
        photo_hash = w3.keccak(text=file_id).hex()
        journal = await get_journal_data(user_id)
        if journal and journal.get("awaiting_photo"):
            # Journal entry photo received - build transaction
            session = await get_session(user_id)
            wallet_address = session.get("wallet_address") if session else None
            if not wallet_address:
                await update.message.reply_text("Wallet not connected. Use /connectwallet first!")
                return

            checksum_address = w3.to_checksum_address(wallet_address)
            location_id = journal.get("location_id")
            telegram_id = int(user_id)

            # Build V2 addJournalEntry transaction (free - rewards TOURS)
            # addJournalEntry(locationId, authorFid, authorTelegramId, entryText, photoIPFS)
            nonce = await w3.eth.get_transaction_count(checksum_address)
            tx = await contract.functions.addJournalEntry(
                location_id, 0, telegram_id, "", photo_hash
            ).build_transaction({
                'chainId': 143,
                'from': checksum_address,
                'nonce': nonce,
                'gas': 500000,
                'gas_price': await w3.eth.gas_price
            })

            await set_pending_wallet(user_id, {
                "awaiting_tx": True,
                "tx_data": tx,
                "wallet_address": checksum_address,
                "timestamp": time.time(),
                "entry_type": "journal",
                "photo_hash": photo_hash
            })

            await update.message.reply_text(
                f"Photo received for Location #{location_id}!\n\n"
                f"Please open https://version1-production.up.railway.app/public/connect.html?userId={user_id} "
                f"to sign the transaction.\n"
                f"This will mint your Climb Proof NFT and earn you 1-10 TOURS!"
            )

            # Clear journal data
            await set_journal_data(user_id, None)
            logger.info(f"/handle_photo journal transaction prepared for user {user_id}, location {location_id}, took {time.time() - start_time:.2f} seconds")
        elif 'pending_climb' in context.user_data:
            pending_climb = context.user_data['pending_climb']
            if pending_climb['user_id'] != user_id:
                await update.message.reply_text("Pending climb belongs to another user. Start with /buildaclimb. 😅")
                logger.info(f"/handle_photo failed: user mismatch for user {user_id}, took {time.time() - start_time:.2f} seconds")
                return
            pending_climb['photo_hash'] = photo_hash
            await update.message.reply_text(
                "Photo received (hashed for efficiency)! 📸 Please share the location of the climb (latitude, longitude).",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Share Location", request_location=True)]], one_time_keyboard=True)
            )
            logger.info(f"/handle_photo processed for climb, awaiting location for user {user_id}, took {time.time() - start_time:.2f} seconds")
        else:
            await update.message.reply_text("No climb or journal creation in progress. Start with /buildaclimb or /journal. 😅")
            logger.info(f"/handle_photo failed: no pending climb or journal for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /handle_photo for user {user_id}: {str(e)}")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error processing photo: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
        logger.info(f"/handle_photo failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def viewclimb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /viewclimb command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not w3 or not contract:
        await update.message.reply_text("Blockchain connection unavailable. Try again later! 😅")
        logger.info(f"/viewclimb failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        if not context.args:
            await update.message.reply_text("Usage: /viewclimb <id>")
            logger.info(f"/viewclimb failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        loc_id = int(context.args[0])
        location = await contract.functions.getClimbingLocation(loc_id).call({'gas': 500000})
        if not location[1]:
            await update.message.reply_text("Climb not found.")
            logger.info(f"/viewclimb failed: climb not found, took {time.time() - start_time:.2f} seconds")
            return
        photo_hash = location[5]
        has_photo = photo_hash != ''
        message = f"🧗 Climb ID: {loc_id} - {location[1]} ({location[2]}) by [{location[0][:6]}...]({EXPLORER_URL}/address/{location[0]})\n   Location: {location[3]/1000000:.6f}, {location[4]/1000000:.6f}\n   Map: https://www.google.com/maps?q={location[3]/1000000:.6f},{location[4]/1000000:.6f}\n   Photo: {'Yes' if has_photo else 'No'}\n   Purchases: {location[10]}\n   Created: {datetime.fromtimestamp(location[6]).strftime('%Y-%m-%d %H:%M:%S')}"
        await update.message.reply_text(message, parse_mode="Markdown")
        logger.info(f"/viewclimb details for {loc_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /viewclimb: {str(e)}")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error retrieving climb: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
        logger.info(f"/viewclimb failed due to error, took {time.time() - start_time:.2f} seconds")

async def buildaclimb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /buildaclimb command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /buildaclimb command disabled")
        await update.message.reply_text("Climb creation unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/buildaclimb failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract or not tours_contract:
        logger.error("Web3 or contract not initialized, /buildaclimb command disabled")
        await update.message.reply_text("Climb creation unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/buildaclimb failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Use: /buildaclimb [name] [difficulty] 🪨 (e.g., /buildaclimb TestClimb Easy)")
            logger.info(f"/buildaclimb failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        name = args[0]
        difficulty = args[1]
        if len(name) > 32 or len(difficulty) > 16:
            await update.message.reply_text("Name (max 32 chars) or difficulty (max 16 chars) too long. Try again! 😅")
            logger.info(f"/buildaclimb failed due to invalid name or difficulty length, took {time.time() - start_time:.2f} seconds")
            return
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("No wallet connected. Use /connectwallet first! 🪙")
            logger.info(f"/buildaclimb failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        logger.info(f"Wallet address for user {user_id}: {wallet_address}")

        # Verify Web3 connection
        is_connected = await w3.is_connected()
        if not is_connected:
            logger.error("Web3 not connected to Monad")
            await update.message.reply_text("Blockchain connection failed. Try again later or contact support at <a href=\"https://t.me/empowertourschat\">EmpowerTours Chat</a>. 😅", parse_mode="HTML")
            logger.info(f"/buildaclimb failed due to Web3 connection, took {time.time() - start_time:.2f} seconds")
            return

        # Ensure checksum address
        try:
            checksum_address = w3.to_checksum_address(wallet_address)
            logger.info(f"Using contract address: {contract.address}")
        except Exception as e:
            logger.error(f"Error converting wallet address to checksum: {str(e)}")
            error_msg = html.escape(str(e))
            await update.message.reply_text(f"Invalid wallet address format: {error_msg}. Try /connectwallet again. 😅", parse_mode="HTML")
            logger.info(f"/buildaclimb failed due to checksum error, took {time.time() - start_time:.2f} seconds")
            return

        # Check for duplicate climb name (V2: locationCount + locations(i))
        try:
            location_count = await contract.functions.locationCount().call({'gas': 500000})
            coros = [contract.functions.locations(i).call({'gas': 500000}) for i in range(1, location_count + 1)]
            locations_list = await asyncio.gather(*coros, return_exceptions=True)
            for loc in locations_list:
                if isinstance(loc, Exception):
                    continue
                # V2 locations tuple: (id, creator, creatorFid, creatorTelegramId, name, difficulty, lat, lon, photoProofIPFS, description, priceWmon, isActive)
                if loc[4].lower() == name.lower():
                    await update.message.reply_text(
                        f"Climb name '{name}' already exists. Choose a unique name (e.g., {name}2025). 😅"
                    )
                    logger.info(f"/buildaclimb failed: duplicate name {name}, took {time.time() - start_time:.2f} seconds")
                    return
        except Exception as e:
            logger.error(f"Error checking existing climbs: {str(e)}")

        # Store pending climb request
        context.user_data['pending_climb'] = {
            'name': name,
            'difficulty': difficulty,
            'user_id': user_id,
            'wallet_address': checksum_address,
            'timestamp': time.time()
        }
        await update.message.reply_text(
            f"Please send a photo for the climb '{name}' ({difficulty}). 📸"
        )
        logger.info(f"/buildaclimb initiated for user {user_id}, awaiting photo, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /buildaclimb for user {user_id}: {str(e)}")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Unexpected error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
        logger.info(f"/buildaclimb failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.FIND_LOCATION)
    start_time = time.time()
    logger.info(f"Received location from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not update.message.location:
        logger.info(f"No location in message, ignoring, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text("No location received. Please share a valid location. 😅")
        return
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, location handling disabled")
        await update.message.reply_text("Location processing unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/handle_location failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract or not wmon_contract:
        logger.error("Web3 not initialized, location handling disabled")
        await update.message.reply_text("Location processing unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/handle_location failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        telegram_id = int(user_id)
        journal = await get_journal_data(user_id)
        if journal and journal.get("awaiting_location"):
            # V2: Journal entry is FREE - user earns TOURS rewards
            session = await get_session(user_id)
            wallet_address = session.get("wallet_address") if session else None
            if not wallet_address:
                await update.message.reply_text("No wallet connected. Use /connectwallet first! 🪙")
                logger.info(f"/handle_location failed due to missing wallet for journal, took {time.time() - start_time:.2f} seconds")
                return
            checksum_address = w3.to_checksum_address(wallet_address)
            location_id = journal.get("location_id", 0)
            entry_text = journal.get("content", "")
            photo_ipfs = journal.get("photo_hash", "")

            # Build V2 addJournalEntry transaction (no cost - rewards TOURS)
            try:
                nonce = await w3.eth.get_transaction_count(checksum_address)
                tx = await contract.functions.addJournalEntry(
                    location_id, 0, telegram_id, entry_text, photo_ipfs
                ).build_transaction({
                    'chainId': 143,
                    'from': checksum_address,
                    'nonce': nonce,
                    'gas': 500000,
                    'gas_price': await w3.eth.gas_price
                })
                await set_pending_wallet(user_id, {
                    "awaiting_tx": True,
                    "tx_data": tx,
                    "wallet_address": checksum_address,
                    "timestamp": time.time(),
                    "entry_type": "journal",
                    "photo_hash": photo_ipfs
                })
                await update.message.reply_text(
                    f"Please open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for journal entry. Earn 1-10 TOURS!"
                )
                await delete_journal_data(user_id)
                logger.info(f"/handle_location processed for journal (V2), transaction built, took {time.time() - start_time:.2f} seconds")
                return
            except Exception as e:
                logger.error(f"Error building journal transaction: {str(e)}")
                error_msg = html.escape(str(e))
                support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
                await update.message.reply_text(f"Failed to build journal transaction: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
                logger.info(f"/handle_location failed due to journal tx build, took {time.time() - start_time:.2f} seconds")
                return
        elif 'pending_climb' in context.user_data:
            # V2: Climb creation uses WMON (35 WMON)
            pending_climb = context.user_data['pending_climb']
            if pending_climb['user_id'] != user_id:
                await update.message.reply_text("Pending climb belongs to another user. Start with /buildaclimb. 😅")
                logger.info(f"/handle_location failed: user mismatch for user {user_id}, took {time.time() - start_time:.2f} seconds")
                return
            latitude = int(update.message.location.latitude * 10**6)
            longitude = int(update.message.location.longitude * 10**6)
            if not (-90 * 10**6 <= latitude <= 90 * 10**6 and -180 * 10**6 <= longitude <= 180 * 10**6):
                await update.message.reply_text("Invalid coordinates. Latitude must be -90 to 90, longitude -180 to 180. Try again! 😅")
                logger.info(f"/handle_location failed: invalid coordinates for user {user_id}, took {time.time() - start_time:.2f} seconds")
                return
            checksum_address = pending_climb['wallet_address']
            name = pending_climb['name']
            difficulty = pending_climb['difficulty']
            photo_hash = pending_climb.get('photo_hash', '')
            description = pending_climb.get('description', '')
            price_wmon = pending_climb.get('price_wmon', w3.to_wei(1, 'ether'))  # default 1 WMON access price

            # Check WMON balance and allowance for location creation fee
            try:
                location_fee = await contract.functions.locationCreationFee().call({'gas': 500000})
                wmon_balance = await wmon_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
                logger.info(f"WMON balance for {checksum_address}: {wmon_balance / 10**18} WMON, fee: {location_fee / 10**18} WMON")
                if wmon_balance < location_fee:
                    await update.message.reply_text(
                        f"Insufficient WMON. Need {location_fee / 10**18} WMON, you have {wmon_balance / 10**18}. Wrap MON to WMON first! 😅"
                    )
                    logger.info(f"/handle_location failed: insufficient WMON for user {user_id}, took {time.time() - start_time:.2f} seconds")
                    return
                allowance = await wmon_contract.functions.allowance(checksum_address, contract.address).call({'gas': 500000})
                logger.info(f"WMON allowance for {checksum_address}: {allowance / 10**18} WMON")
                if allowance < location_fee:
                    nonce = await w3.eth.get_transaction_count(checksum_address)
                    approve_tx = await wmon_contract.functions.approve(contract.address, location_fee).build_transaction({
                        'chainId': 143,
                        'from': checksum_address,
                        'nonce': nonce,
                        'gas': 100000,
                        'gas_price': await w3.eth.gas_price
                    })
                    await set_pending_wallet(user_id, {
                        "awaiting_tx": True,
                        "tx_data": approve_tx,
                        "wallet_address": checksum_address,
                        "timestamp": time.time(),
                        "next_tx": {
                            "type": "create_climbing_location",
                            "name": name,
                            "difficulty": difficulty,
                            "latitude": latitude,
                            "longitude": longitude,
                            "photo_hash": photo_hash,
                            "description": description,
                            "price_wmon": price_wmon
                        },
                        "entry_type": "climb",
                        "photo_hash": photo_hash
                    })
                    await update.message.reply_text(
                        f"Please open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to approve {location_fee / 10**18} WMON for climb creation."
                    )
                    logger.info(f"/handle_location initiated WMON approval for user {user_id}, took {time.time() - start_time:.2f} seconds")
                    return
            except Exception as e:
                logger.error(f"Error checking WMON balance or allowance: {str(e)}")
                error_msg = html.escape(str(e))
                support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
                await update.message.reply_text(f"Failed to check WMON balance or allowance: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
                logger.info(f"/handle_location failed due to WMON balance/allowance error, took {time.time() - start_time:.2f} seconds")
                return

            # Simulate V2 createLocation
            try:
                await contract.functions.createLocation(
                    0, telegram_id, name, difficulty, latitude, longitude, photo_hash, description, price_wmon
                ).call({
                    'from': checksum_address,
                    'gas': 500000
                })
            except Exception as e:
                revert_reason = html.escape(str(e))
                logger.error(f"createLocation simulation failed: {revert_reason}")
                support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
                await update.message.reply_text(
                    f"Transaction simulation failed: {revert_reason}. Check parameters (name, difficulty, coordinates) or contact support at {support_link}. 😅",
                    parse_mode="HTML"
                )
                logger.info(f"/handle_location failed due to simulation error, took {time.time() - start_time:.2f} seconds")
                return

            # Build V2 createLocation transaction
            try:
                nonce = await w3.eth.get_transaction_count(checksum_address)
                tx = await contract.functions.createLocation(
                    0, telegram_id, name, difficulty, latitude, longitude, photo_hash, description, price_wmon
                ).build_transaction({
                    'chainId': 143,
                    'from': checksum_address,
                    'nonce': nonce,
                    'gas': 500000,
                    'gas_price': await w3.eth.gas_price
                })
                logger.info(f"V2 createLocation transaction built for user {user_id}: {json.dumps(tx, default=str)}")
                await set_pending_wallet(user_id, {
                    "awaiting_tx": True,
                    "tx_data": tx,
                    "wallet_address": checksum_address,
                    "timestamp": time.time(),
                    "name": name,
                    "difficulty": difficulty,
                    "latitude": latitude,
                    "longitude": longitude,
                    "photo_hash": photo_hash,
                    "entry_type": "climb"
                })
                await update.message.reply_text(
                    f"Please open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for climb '{name}' ({difficulty}) using {location_fee / 10**18} WMON."
                )
                logger.info(f"/handle_location processed, V2 transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
            except Exception as e:
                logger.error(f"Error building transaction for user {user_id}: {str(e)}")
                error_msg = html.escape(str(e))
                support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
                await update.message.reply_text(f"Failed to build transaction: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
                logger.info(f"/handle_location failed due to transaction build error, took {time.time() - start_time:.2f} seconds")
        else:
            await update.message.reply_text("No climb or journal creation in progress. Start with /buildaclimb or /journal. 😅")
            logger.info(f"/handle_location failed: no pending climb or journal for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /handle_location for user {user_id}: {str(e)}")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Unexpected error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
        logger.info(f"/handle_location failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def purchase_climb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /purchaseclimb command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /purchaseclimb command disabled")
        await update.message.reply_text("Climb purchase unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/purchaseclimb failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract or not wmon_contract:
        logger.error("Web3 not initialized, /purchaseclimb command disabled")
        await update.message.reply_text("Climb purchase unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/purchaseclimb failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        telegram_id = int(user_id)
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Use: /purchaseclimb [id] 🪙")
            logger.info(f"/purchaseclimb failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        location_id = int(args[0])
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            logger.info(f"/purchaseclimb failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        checksum_address = w3.to_checksum_address(wallet_address)
        # Check if already purchased (via Envio)
        already_purchased = await has_purchased_climb(checksum_address, location_id)
        if already_purchased:
            await update.message.reply_text(f"You have already purchased climb #{location_id}. Check /mypurchases! 😅")
            logger.info(f"/purchaseclimb failed: already purchased climb {location_id} for user {user_id}, took {time.time() - start_time:.2f} seconds")
            return
        # V2: Get location's WMON price from contract
        location_data = await contract.functions.locations(location_id).call({'gas': 500000})
        purchase_cost = location_data[10]  # priceWmon field
        logger.info(f"Location #{location_id} price: {purchase_cost / 10**18} WMON")
        # Check WMON balance
        wmon_balance = await wmon_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
        if wmon_balance < purchase_cost:
            await update.message.reply_text(
                f"Insufficient WMON. Need {purchase_cost / 10**18} WMON, you have {wmon_balance / 10**18}. Wrap MON to WMON first! 😅"
            )
            logger.info(f"/purchaseclimb failed: insufficient WMON for user {user_id}, took {time.time() - start_time:.2f} seconds")
            return
        # Check WMON allowance
        allowance = await wmon_contract.functions.allowance(checksum_address, contract.address).call({'gas': 500000})
        if allowance < purchase_cost:
            nonce = await w3.eth.get_transaction_count(checksum_address)
            approve_tx = await wmon_contract.functions.approve(contract.address, purchase_cost).build_transaction({
                'chainId': 143,
                'from': checksum_address,
                'nonce': nonce,
                'gas': 100000,
                'gas_price': await w3.eth.gas_price
            })
            await set_pending_wallet(user_id, {
                "awaiting_tx": True,
                "tx_data": approve_tx,
                "wallet_address": checksum_address,
                "timestamp": time.time(),
                "next_tx": {
                    "type": "purchase_climbing_location",
                    "location_id": location_id
                }
            })
            await update.message.reply_text(
                f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to approve {purchase_cost / 10**18} WMON for climb purchase using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})). After approval, you'll sign the purchase transaction.",
                parse_mode="Markdown"
            )
            logger.info(f"/purchaseclimb initiated WMON approval for user {user_id}, took {time.time() - start_time:.2f} seconds")
            return
        # If allowance OK, build V2 purchase tx
        nonce = await w3.eth.get_transaction_count(checksum_address)
        tx = await contract.functions.purchaseLocation(location_id, 0, telegram_id).build_transaction({
            'chainId': 143,
            'from': checksum_address,
            'nonce': nonce,
            'gas': 300000,
            'gas_price': await w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for climb purchase ({purchase_cost / 10**18} WMON) using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})).",
            parse_mode="Markdown"
        )
        await set_pending_wallet(user_id, {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": checksum_address,
            "timestamp": time.time()
        })
        logger.info(f"/purchaseclimb V2 transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /purchaseclimb: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def findaclimb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /findaclimb command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not w3 or not contract:
        await update.message.reply_text("Blockchain connection unavailable. Try again later! 😅")
        logger.info(f"/findaclimb failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        global climb_cache, cache_timestamp
        current_time = time.time()
        if climb_cache and current_time - cache_timestamp < CACHE_TTL:
            tour_list = climb_cache
        else:
            location_count = await contract.functions.locationCount().call({'gas': 500000})
            logger.info(f"V2 location count: {location_count}")
            if location_count == 0:
                await update.message.reply_text("No climbs found. Create one with /buildaclimb! 🪨")
                logger.info(f"/findaclimb found no climbs, took {time.time() - start_time:.2f} seconds")
                return
            # V2: locations are 1-indexed
            coros = [contract.functions.locations(i).call({'gas': 500000}) for i in range(1, location_count + 1)]
            locations_list = await asyncio.gather(*coros, return_exceptions=True)
            tour_list = []
            for loc in locations_list:
                if isinstance(loc, Exception):
                    logger.error(f"Error retrieving climb: {str(loc)}")
                    continue
                # V2 tuple: (id, creator, creatorFid, creatorTelegramId, name, difficulty, lat, lon, photoProofIPFS, description, priceWmon, isActive)
                if not loc[11]:  # isActive
                    continue
                loc_id = loc[0]
                creator = loc[1]
                name = loc[4]
                difficulty = loc[5]
                lat = loc[6] / 1000000
                lon = loc[7] / 1000000
                photo_info = " (has photo)" if loc[8] else ""
                price_wmon = loc[10] / 10**18
                tour_list.append(
                    f"🧗 Climb #{loc_id} - {name}{photo_info} ({difficulty}) by [{creator[:6]}...]({EXPLORER_URL}/address/{creator})\n"
                    f"   Location: {lat:.6f},{lon:.6f}\n"
                    f"   Map: https://www.google.com/maps?q={lat:.6f},{lon:.6f}\n"
                    f"   Access price: {price_wmon} WMON"
                )
            climb_cache = tour_list
            cache_timestamp = current_time
        if not tour_list:
            await update.message.reply_text("No climbs found. Create one with /buildaclimb! 🪨")
        else:
            await update.message.reply_text("\n\n".join(tour_list), parse_mode="Markdown")
        logger.info(f"/findaclimb retrieved {len(tour_list)} climbs, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /findaclimb: {str(e)}")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error retrieving climbs: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
        logger.info(f"/findaclimb failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /balance command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        user_id = str(update.effective_user.id)
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("No wallet connected. Use /connectwallet first! 🪙")
            logger.info(f"/balance failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        logger.info(f"Wallet address for user {user_id}: {wallet_address}")
        
        # Verify Web3 connection
        is_connected = await w3.is_connected()
        if not is_connected:
            logger.error("Web3 not connected to Monad")
            await update.message.reply_text("Blockchain connection failed. Try again later or contact support at <a href=\"https://t.me/empowertourschat\">EmpowerTours Chat</a>. 😅", parse_mode="HTML")
            logger.info(f"/balance failed due to Web3 connection, took {time.time() - start_time:.2f} seconds")
            return

        # Ensure checksum address
        try:
            checksum_address = w3.to_checksum_address(wallet_address)
        except Exception as e:
            logger.error(f"Error converting wallet address to checksum: {str(e)}")
            error_msg = html.escape(str(e))
            await update.message.reply_text(f"Invalid wallet address format: {error_msg}. Try /connectwallet again. 😅", parse_mode="HTML")
            logger.info(f"/balance failed due to checksum error, took {time.time() - start_time:.2f} seconds")
            return

        # Get balances
        try:
            mon_balance = await w3.eth.get_balance(checksum_address)
            tours_balance = await tours_contract.functions.balanceOf(checksum_address).call()
            wmon_balance = await wmon_contract.functions.balanceOf(checksum_address).call()
            await update.message.reply_text(
                f"Wallet Balance:\n"
                f"- {mon_balance / 10**18:.4f} $MON\n"
                f"- {wmon_balance / 10**18:.4f} WMON\n"
                f"- {tours_balance / 10**18:.4f} $TOURS\n"
                f"Address: [{checksum_address}]({EXPLORER_URL}/address/{checksum_address})\n"
                f"\nUse /wrapmon to convert MON to WMON for transactions",
                parse_mode="Markdown"
            )
            logger.info(f"/balance retrieved for user {user_id}, took {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error retrieving balance for user {user_id}: {str(e)}")
            error_msg = html.escape(str(e))
            support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
            await update.message.reply_text(f"Failed to retrieve balance: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
            logger.info(f"/balance failed due to balance error, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /balance for user {user_id}: {str(e)}")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Unexpected error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")
        logger.info(f"/balance failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def wrapmon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrap MON to WMON - /wrapmon [amount]"""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received /wrapmon command from user {user_id}")
    try:
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("No wallet connected. Use /connectwallet first!")
            return

        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /wrapmon [amount]\n"
                "Example: /wrapmon 10\n\n"
                "This wraps your MON into WMON, which is required for creating and purchasing climbs."
            )
            return

        try:
            amount = float(context.args[0])
            if amount <= 0:
                await update.message.reply_text("Amount must be greater than 0.")
                return
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a number.")
            return

        checksum_address = w3.to_checksum_address(wallet_address)
        amount_wei = int(amount * 10**18)

        # Check MON balance
        mon_balance = await w3.eth.get_balance(checksum_address)
        if mon_balance < amount_wei:
            await update.message.reply_text(
                f"Insufficient MON balance.\n"
                f"You have: {mon_balance / 10**18:.4f} MON\n"
                f"You need: {amount} MON"
            )
            return

        # Build wrap transaction (deposit function with value)
        nonce = await w3.eth.get_transaction_count(checksum_address)
        gas_price = await w3.eth.gas_price
        tx = {
            'to': w3.to_checksum_address(WMON_ADDRESS),
            'value': amount_wei,
            'gas': 50000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 143,
            'data': wmon_contract.encodeABI(fn_name='deposit')
        }

        # Create MetaMask deeplink
        tx_data_hex = tx['data']
        metamask_url = f"https://metamask.app.link/send/{WMON_ADDRESS}@143?value={amount_wei}&data={tx_data_hex}"

        keyboard = [
            [InlineKeyboardButton("Sign in MetaMask", url=metamask_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Wrap {amount} MON to WMON:\n\n"
            f"Click below to sign the transaction in MetaMask.\n"
            f"After signing, your WMON balance will update.",
            reply_markup=reply_markup
        )
        logger.info(f"/wrapmon transaction prepared for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /wrapmon: {str(e)}")
        await update.message.reply_text(f"Error: {escape_html(str(e))}. Try again or contact support.", parse_mode="HTML")

async def unwrapmon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unwrap WMON to MON - /unwrapmon [amount]"""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received /unwrapmon command from user {user_id}")
    try:
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("No wallet connected. Use /connectwallet first!")
            return

        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /unwrapmon [amount]\n"
                "Example: /unwrapmon 10\n\n"
                "This unwraps your WMON back to MON."
            )
            return

        try:
            amount = float(context.args[0])
            if amount <= 0:
                await update.message.reply_text("Amount must be greater than 0.")
                return
        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a number.")
            return

        checksum_address = w3.to_checksum_address(wallet_address)
        amount_wei = int(amount * 10**18)

        # Check WMON balance
        wmon_balance = await wmon_contract.functions.balanceOf(checksum_address).call()
        if wmon_balance < amount_wei:
            await update.message.reply_text(
                f"Insufficient WMON balance.\n"
                f"You have: {wmon_balance / 10**18:.4f} WMON\n"
                f"You need: {amount} WMON"
            )
            return

        # Build unwrap transaction (withdraw function)
        nonce = await w3.eth.get_transaction_count(checksum_address)
        gas_price = await w3.eth.gas_price
        tx_data = wmon_contract.encodeABI(fn_name='withdraw', args=[amount_wei])
        tx = {
            'to': w3.to_checksum_address(WMON_ADDRESS),
            'value': 0,
            'gas': 50000,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 143,
            'data': tx_data
        }

        # Create MetaMask deeplink
        metamask_url = f"https://metamask.app.link/send/{WMON_ADDRESS}@143?data={tx_data}"

        keyboard = [
            [InlineKeyboardButton("Sign in MetaMask", url=metamask_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Unwrap {amount} WMON to MON:\n\n"
            f"Click below to sign the transaction in MetaMask.\n"
            f"After signing, your MON balance will update.",
            reply_markup=reply_markup
        )
        logger.info(f"/unwrapmon transaction prepared for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /unwrapmon: {str(e)}")
        await update.message.reply_text(f"Error: {escape_html(str(e))}. Try again or contact support.", parse_mode="HTML")

async def mynfts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View user's NFTs - /mynfts"""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received /mynfts command from user {user_id}")
    try:
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("No wallet connected. Use /connectwallet first!")
            return

        checksum_address = w3.to_checksum_address(wallet_address)

        # Get Access Badges (purchases) and Climb Proofs (journals)
        access_badges = await get_user_purchases(checksum_address)
        climb_proofs = await get_user_climb_proofs(checksum_address)

        if not access_badges and not climb_proofs:
            await update.message.reply_text(
                "You don't have any NFTs yet!\n\n"
                "- Purchase a climb with /purchaseclimb to get an Access Badge\n"
                "- Log a climb with /journal to earn a Climb Proof NFT"
            )
            return

        message = "Your NFTs:\n\n"

        if access_badges:
            message += f"Access Badges ({len(access_badges)}):\n"
            for badge in access_badges[:10]:  # Limit to 10
                token_id = badge.get("tokenId", "?")
                location_id = badge.get("locationId", "?")
                message += f"  #{token_id} - Location #{location_id}\n"
            if len(access_badges) > 10:
                message += f"  ... and {len(access_badges) - 10} more\n"
            message += "\n"

        if climb_proofs:
            message += f"Climb Proofs ({len(climb_proofs)}):\n"
            for proof in climb_proofs[:10]:  # Limit to 10
                token_id = proof.get("tokenId", "?")
                location_id = proof.get("locationId", "?")
                tours = int(proof.get("toursRewarded", 0)) / 10**18
                message += f"  #{token_id} - Location #{location_id} (+{tours:.0f} TOURS)\n"
            if len(climb_proofs) > 10:
                message += f"  ... and {len(climb_proofs) - 10} more\n"

        message += f"\nUse /viewnft [id] to view details"
        await update.message.reply_text(message)
        logger.info(f"/mynfts success for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /mynfts: {str(e)}")
        await update.message.reply_text(f"Error: {escape_html(str(e))}. Try again or contact support.", parse_mode="HTML")

async def viewnft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View specific NFT details - /viewnft [id]"""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received /viewnft command from user {user_id}")
    try:
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /viewnft [token_id]\n"
                "Example: /viewnft 1\n\n"
                "Use /mynfts to see your NFT IDs."
            )
            return

        try:
            token_id = int(context.args[0])
            if token_id <= 0:
                await update.message.reply_text("Token ID must be a positive number.")
                return
        except ValueError:
            await update.message.reply_text("Invalid token ID. Please enter a number.")
            return

        nft = await get_nft_by_id(token_id)
        if not nft:
            await update.message.reply_text(f"NFT #{token_id} not found.")
            return

        nft_type = nft.get("nftType", "Unknown")
        location_id = nft.get("locationId", "?")
        holder = nft.get("holder", "?")

        message = f"{nft_type} #{token_id}\n\n"
        message += f"Location: #{location_id}\n"
        message += f"Holder: <a href=\"{EXPLORER_URL}/address/{holder}\">{holder[:10]}...</a>\n"

        if nft_type == "Access Badge":
            purchased_at = nft.get("purchasedAt", "Unknown")
            message += f"Purchased: {purchased_at}\n"
        else:
            minted_at = nft.get("mintedAt", "Unknown")
            tours = int(nft.get("toursRewarded", 0)) / 10**18
            photo_hash = nft.get("photoHash", "")
            message += f"Minted: {minted_at}\n"
            message += f"TOURS Rewarded: {tours:.0f}\n"
            if photo_hash:
                message += f"Photo: <a href=\"https://ipfs.io/ipfs/{photo_hash}\">View</a>\n"

        message += f"\nContract: <a href=\"{EXPLORER_URL}/token/{CLIMBING_V2_ADDRESS}?a={token_id}\">View on Explorer</a>"
        await update.message.reply_text(message, parse_mode="HTML")
        logger.info(f"/viewnft success for token {token_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /viewnft: {str(e)}")
        await update.message.reply_text(f"Error: {escape_html(str(e))}. Try again or contact support.", parse_mode="HTML")

async def mypurchases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /mypurchases command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        session = await get_session(str(update.effective_user.id))
        if not session or not session.get("wallet_address"):
            await update.message.reply_text("Connect your wallet with /connectwallet first! 😅")
            logger.info(f"/mypurchases failed due to no wallet, took {time.time() - start_time:.2f} seconds")
            return
        wallet_address = session["wallet_address"]
        checksum_address = w3.to_checksum_address(wallet_address) if w3 else wallet_address  # Fallback if w3 unavailable

        # Query Envio for purchases
        purchases = await get_user_purchases(checksum_address)

        if not purchases:
            await update.message.reply_text("No purchased climbs found. Use /purchaseclimb to buy one! 😅")
            logger.info(f"/mypurchases no purchases found, took {time.time() - start_time:.2f} seconds")
            return

        await update.message.reply_text("Your purchased climbs:")
        for purchase in purchases:
            location_id = int(purchase.get("locationId", 0))
            purchased_at = purchase.get("purchasedAt", "")
            climb = await contract.functions.getClimbingLocation(location_id).call()
            message = f"🏔️ #{location_id} {escape_html(climb[1])} ({escape_html(climb[2])}) - Purchased {purchased_at}\n"
            message += f"   Creator: <a href=\"{EXPLORER_URL}/address/{climb[0]}\">{climb[0][:6]}...</a>\n"
            message += f"   Location: ({climb[3]/10**6:.4f}, {climb[4]/10**6:.4f})\n"
            message += f"   Map: https://www.google.com/maps?q={climb[3]/10**6},{climb[4]/10**6}\n"
            message += f"   Purchases: {climb[10]}\n"
            await update.message.reply_text(message, parse_mode="HTML")

        logger.info(f"/mypurchases success with {len(purchases)} purchases, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /mypurchases: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error retrieving purchases: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def handle_tx_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received transaction hash from user {user_id}: {update.message.text} in chat {update.effective_chat.id}")
    pending = await get_pending_wallet(user_id)
    if not pending or not pending.get("awaiting_tx"):
        logger.warning(f"No pending transaction for user {user_id}")
        await update.message.reply_text("No pending transaction found. Use /buildaclimb, /journal, or /purchaseclimb to start a new action! 😅")
        logger.info(f"/handle_tx_hash no pending transaction, took {time.time() - start_time:.2f} seconds")
        return
    if not w3:
        logger.error("Web3 not initialized, transaction handling disabled")
        await update.message.reply_text("Transaction handling unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/handle_tx_hash failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    tx_hash = update.message.text.strip()
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        await update.message.reply_text("Invalid transaction hash. Send a valid hash (e.g., 0x123...).")
        logger.info(f"/handle_tx_hash failed due to invalid hash, took {time.time() - start_time:.2f} seconds")
        return
    try:
        receipt = await w3.eth.get_transaction_receipt(tx_hash)
        if receipt and receipt.status:
            entry_type = pending.get("entry_type", "")
            action = "Action completed"
            if entry_type == "climb":
                action = f"Climb '{pending.get('name', 'Unknown')}' ({pending.get('difficulty', 'Unknown')}) created"
            elif entry_type == "journal":
                action = "Journal entry submitted! You earned TOURS"
            await update.message.reply_text(f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 {action}.", parse_mode="Markdown")
            if CHAT_HANDLE and TELEGRAM_TOKEN:
                message = f"New activity by {escape_html(update.effective_user.username or update.effective_user.first_name)} on EmpowerTours! 🧗 <a href=\"{EXPLORER_URL}/tx/{tx_hash}\">Tx: {escape_html(tx_hash)}</a>"
                await send_notification(CHAT_HANDLE, message)
            if pending.get("next_tx"):
                next_tx_data = pending["next_tx"]
                telegram_id = int(user_id)
                if next_tx_data["type"] == "create_climbing_location":
                    nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                    tx = await contract.functions.createLocation(
                        0, telegram_id,
                        next_tx_data["name"],
                        next_tx_data["difficulty"],
                        next_tx_data["latitude"],
                        next_tx_data["longitude"],
                        next_tx_data["photo_hash"],
                        next_tx_data.get("description", ""),
                        next_tx_data.get("price_wmon", w3.to_wei(1, 'ether'))
                    ).build_transaction({
                        'chainId': 143,
                        'from': pending["wallet_address"],
                        'nonce': nonce,
                        'gas': 500000,
                        'gas_price': await w3.eth.gas_price
                    })
                    await set_pending_wallet(user_id, {
                        "awaiting_tx": True,
                        "tx_data": tx,
                        "wallet_address": pending["wallet_address"],
                        "timestamp": time.time(),
                        "name": next_tx_data["name"],
                        "difficulty": next_tx_data["difficulty"],
                        "latitude": next_tx_data["latitude"],
                        "longitude": next_tx_data["longitude"],
                        "photo_hash": next_tx_data["photo_hash"]
                    })
                    await update.message.reply_text(
                        f"WMON approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for climb '{next_tx_data['name']}' ({next_tx_data['difficulty']})."
                    )
                    logger.info(f"/handle_tx_hash processed WMON approval, next transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
                    return
                elif next_tx_data["type"] == "purchase_climbing_location":
                    nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                    tx = await contract.functions.purchaseLocation(
                        next_tx_data["location_id"], 0, telegram_id
                    ).build_transaction({
                        'chainId': 143,
                        'from': pending["wallet_address"],
                        'nonce': nonce,
                        'gas': 300000,
                        'gas_price': await w3.eth.gas_price
                    })
                    await set_pending_wallet(user_id, {
                        "awaiting_tx": True,
                        "tx_data": tx,
                        "wallet_address": pending["wallet_address"],
                        "timestamp": time.time()
                    })
                    await update.message.reply_text(
                        f"WMON approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for purchasing climb #{next_tx_data['location_id']}."
                    )
                    logger.info(f"/handle_tx_hash processed WMON approval, next transaction built for purchase_climb, took {time.time() - start_time:.2f} seconds")
                    return
            await delete_pending_wallet(user_id)
            logger.info(f"/handle_tx_hash confirmed for user {user_id}, took {time.time() - start_time:.2f} seconds")
        else:
            await update.message.reply_text("Transaction failed or pending. Check and try again! 😅")
            logger.info(f"/handle_tx_hash failed or pending, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in handle_tx_hash: {str(e)}, took {time.time() - start_time:.2f} seconds")
        error_msg = html.escape(str(e))
        support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
        await update.message.reply_text(f"Error: {error_msg}. Try again or contact support at {support_link}. 😅", parse_mode="HTML")

async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    device_info = (
        f"via_bot={update.message.via_bot.id if update.message.via_bot else 'none'}, "
        f"chat_type={update.message.chat.type}, "
        f"platform={getattr(update.message.via_bot, 'platform', 'unknown')}"
    )
    logger.info(f"Received text message from user {update.effective_user.id} in chat {update.effective_chat.id}: {update.message.text}, {device_info}")
    await update.message.reply_text(
        f"Received message: '{update.message.text}'. Use a valid command like /start or /tutorial. 😅\nDebug: {device_info}"
    )
    logger.info(f"Processed non-command text message, took {time.time() - start_time:.2f} seconds")
    
async def get_session(user_id):
    return sessions.get(user_id)

async def set_session(user_id, wallet_address):
    global sessions, reverse_sessions
    sessions[user_id] = {"wallet_address": wallet_address}
    if wallet_address:
        reverse_sessions[wallet_address] = user_id

async def get_pending_wallet(user_id):
    return pending_wallets.get(user_id)

async def set_pending_wallet(user_id, data):
    global pending_wallets
    pending_wallets[user_id] = data

async def delete_pending_wallet(user_id):
    global pending_wallets
    if user_id in pending_wallets:
        del pending_wallets[user_id]

async def get_journal_data(user_id):
    return journal_data.get(user_id)

async def set_journal_data(user_id, data):
    global journal_data
    journal_data[user_id] = data

async def delete_journal_data(user_id):
    global journal_data
    if user_id in journal_data:
        del journal_data[user_id]

async def startup_event():
    start_time = time.time()
    global application, webhook_failed, sessions, reverse_sessions, pending_wallets, journal_data
    try:
        # In-memory session storage initialized at module level
        # Blockchain data is fetched from Envio GraphQL as needed
        logger.info(f"Using Envio GraphQL: {ENVIO_GRAPHQL_URL}")
        logger.info("Session storage: in-memory (sessions reset on restart)")

        # Check and free port
        port = int(os.getenv("PORT", 8080))
        ports = [port, 8081]
        selected_port = None
        for p in ports:
            logger.info(f"Checking for port {p} availability")
            for attempt in range(1, 4):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('0.0.0.0', p))
                    sock.close()
                    logger.info(f"Port {p} is available")
                    selected_port = p
                    break
                except socket.error as e:
                    logger.error(f"Port {p} in use on attempt {attempt}/3: {str(e)}. Attempting to free port...")
                    try:
                        result = subprocess.run(
                            f"lsof -i :{p} | grep LISTEN | awk '{{print $2}}' | xargs kill -9",
                            shell=True, capture_output=True, text=True
                        )
                        logger.info(f"Port {p} cleanup result: {result.stdout}, {result.stderr}")
                    except subprocess.SubprocessError as se:
                        logger.error(f"Failed to run cleanup command for port {p}: {str(se)}")
                    time.sleep(2)
                    if attempt == 3:
                        logger.error(f"Failed to free port {p} after 3 attempts.")
                        if p == ports[-1]:
                            logger.error("No available ports. Falling back to polling.")
                            webhook_failed = True
                else:
                    break
            if selected_port:
                break

        if not selected_port:
            logger.error("No ports available, proceeding with polling")
            webhook_failed = True

        logger.info("Starting bot initialization")
        await initialize_web3()

        # Initialize Telegram Application
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        logger.info("Application initialized")

        # Register command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("tutorial", tutorial))
        application.add_handler(CommandHandler("connectwallet", connect_wallet))
        application.add_handler(CommandHandler("help", help))
        application.add_handler(CommandHandler("buildaclimb", buildaclimb))
        application.add_handler(CommandHandler("findaclimb", findaclimb))
        application.add_handler(CommandHandler("viewclimb", viewclimb))
        application.add_handler(CommandHandler("purchaseclimb", purchase_climb))
        application.add_handler(CommandHandler("mypurchases", mypurchases))
        application.add_handler(CommandHandler("journal", journal_entry))
        application.add_handler(CommandHandler("mynfts", mynfts))
        application.add_handler(CommandHandler("viewnft", viewnft))
        application.add_handler(CommandHandler("balance", balance))
        application.add_handler(CommandHandler("wrapmon", wrapmon))
        application.add_handler(CommandHandler("unwrapmon", unwrapmon))
        application.add_handler(CommandHandler("ping", ping))
        application.add_handler(CommandHandler("debug", debug_command))
        application.add_handler(CommandHandler("forcewebhook", forcewebhook))
        application.add_handler(CommandHandler("clearcache", clearcache))
        application.add_handler(MessageHandler(filters.Regex(r'^0x[a-fA-F0-9]{64}$'), handle_tx_hash))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.LOCATION, handle_location))
        application.add_handler(MessageHandler(filters.COMMAND, debug_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
        logger.info("Command handlers registered successfully")

        # monitor_events disabled - using Envio GraphQL for event indexing instead

        # Initialize and start application
        await application.initialize()
        logger.info("Application initialized via initialize()")

        # Set webhook with increased max_connections
        logger.info("Forcing webhook reset on startup")
        webhook_success = await reset_webhook()
        if not webhook_success:
            logger.info("Webhook failed or not set, starting polling")
            await application.start()
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        else:
            logger.info("Webhook set successfully, starting application")
            await application.start()
        webhook_info = await check_webhook()
        logger.info(f"Webhook verification: {webhook_info}")
        logger.info(f"Bot startup complete, took {time.time() - start_time:.2f} seconds")

    except Exception as e:
        logger.error(f"Error in startup_event: {str(e)}, took {time.time() - start_time:.2f} seconds")
        webhook_failed = True
        raise

async def shutdown_event():
    start_time = time.time()
    global application
    logger.info("Received shutdown signal")
    if application:
        try:
            await application.stop()
            await application.updater.stop()
            logger.info(f"Application shutdown complete, took {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}, took {time.time() - start_time:.2f} seconds")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()
    yield
    await shutdown_event()

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/public", StaticFiles(directory="public", html=True), name="public")

@app.get("/public/{path:path}")
async def log_static_access(path: str, request: Request):
    start_time = time.time()
    logger.info(f"Access attempt to static file: /public/{path}, url={request.url}")
    file_path = os.path.join("public", path)
    if not os.path.exists(file_path):
        for fname in os.listdir("public"):
            if fname.lower() == path.lower():
                file_path = os.path.join("public", fname)
                logger.info(f"Found case-insensitive match for {path}: {file_path}")
                break
        else:
            logger.error(f"Static file not found: {file_path}")
            raise HTTPException(status_code=404, detail=f"File {path} not found in public directory")
    response = FileResponse(file_path)
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["ETag"] = f"{os.path.getmtime(file_path)}"
    logger.info(f"/public/{path} served, took {time.time() - start_time:.2f} seconds")
    return response

@app.get("/get_transaction")
async def get_transaction(userId: str):
    start_time = time.time()
    logger.info(f"Received /get_transaction request for user {userId}")
    try:
        pending = await get_pending_wallet(userId)
        if pending and pending.get("awaiting_tx"):
            if pending.get("tx_served", False):
                # Already served once—prevent repeat
                logger.info(f"Transaction already served for user {userId}, ignoring repeat poll")
                return {"transaction": None}
            pending["tx_served"] = True  # Mark as served
            await set_pending_wallet(userId, pending)
            logger.info(f"Transaction served (once) for user {userId}: {pending['tx_data']}, took {time.time() - start_time:.2f} seconds")
            return {"transaction": pending["tx_data"]}
        logger.info(f"No transaction found for user {userId}, took {time.time() - start_time:.2f} seconds")
        return {"transaction": None}
    except Exception as e:
        logger.error(f"Error in /get_transaction for user {userId}: {str(e)}, took {time.time() - start_time:.2f} seconds")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit_wallet")
async def submit_wallet(request: Request):
    start_time = time.time()
    try:
        data = await request.json()
        user_id = data.get("userId")
        wallet_address = data.get("walletAddress")
        if not user_id or not wallet_address:
            logger.error(f"Missing userId or walletAddress in /submit_wallet: {data}")
            raise HTTPException(status_code=400, detail="Missing userId or walletAddress")
        logger.info(f"Received wallet submission for user {user_id}: {wallet_address}")

        # Validate wallet address
        if not w3 or not w3.is_address(wallet_address):
            logger.error(f"Invalid wallet address or Web3 not initialized: {wallet_address}")
            logger.info(f"/submit_wallet failed due to invalid address or Web3, took {time.time() - start_time:.2f} seconds")
            return {"status": "error", "message": "Invalid wallet address"}

        # Process wallet even if not in pending_wallets to handle edge cases
        pending = await get_pending_wallet(user_id)
        if not pending or not pending.get("awaiting_wallet"):
            logger.warning(f"No pending wallet connection for user {user_id}, proceeding anyway")

        # Save the wallet first - this is the critical operation
        checksum_address = w3.to_checksum_address(wallet_address)
        await set_session(user_id, checksum_address)
        await delete_pending_wallet(user_id)
        logger.info(f"/submit_wallet saved wallet for user {user_id}: {checksum_address}")

        # Try to send Telegram notification (non-critical - don't fail if this errors)
        try:
            await application.bot.send_message(
                user_id,
                f"Wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address}) connected! Use /balance to check your status or /buildaclimb to create a climb.",
                parse_mode="Markdown"
            )
        except Exception as tg_error:
            logger.warning(f"Could not send Telegram notification to user {user_id}: {str(tg_error)}")

        logger.info(f"/submit_wallet processed for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /submit_wallet: {str(e)}, took {time.time() - start_time:.2f} seconds")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/submit_tx")
async def submit_tx(request: Request):
    start_time = time.time()
    try:
        data = await request.json()
        user_id = data.get("userId")
        tx_hash = data.get("txHash")
        if isinstance(tx_hash, dict):
            tx_hash = tx_hash.get("transactionHash") or tx_hash.get("txHash")
            logger.info(f"Extracted txHash from object: {tx_hash}")
        if not user_id or not tx_hash:
            logger.error(f"Missing userId or txHash in /submit_tx: {data}")
            raise HTTPException(status_code=400, detail="Missing userId or txHash")
        if not isinstance(tx_hash, str) or not tx_hash.startswith("0x") or len(tx_hash) != 66:
            logger.error(f"Invalid txHash format: {tx_hash}")
            raise HTTPException(status_code=400, detail="Invalid txHash format")
        logger.info(f"Received transaction hash for user {user_id}: {tx_hash}")
        if not w3:
            logger.error("Web3 not initialized, transaction handling disabled")
            raise HTTPException(status_code=500, detail="Blockchain unavailable")
        try:
            receipt = await w3.eth.get_transaction_receipt(tx_hash)
            if receipt and receipt.status:
                pending = await get_pending_wallet(user_id)
                if pending:
                    entry_type = pending.get("entry_type", "")
                    success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 Action completed successfully."
                    if entry_type == "climb":
                        success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪨 Climb '{pending.get('name', 'Unknown')}' ({pending.get('difficulty', 'Unknown')}) created!"
                    elif entry_type == "journal":
                        success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 📝 Journal entry added! You earned TOURS!"
                    if CHAT_HANDLE and TELEGRAM_TOKEN:
                        message = f"New activity by user {user_id} on EmpowerTours! 🧗 <a href=\"{EXPLORER_URL}/tx/{tx_hash}\">Tx: {escape_html(tx_hash)}</a>"
                        await send_notification(CHAT_HANDLE, message)
                    await application.bot.send_message(user_id, success_message, parse_mode="Markdown")
                    if pending.get("next_tx"):
                        next_tx_data = pending["next_tx"]
                        telegram_id = int(user_id)
                        if next_tx_data["type"] == "create_climbing_location":
                            nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                            tx = await contract.functions.createLocation(
                                0, telegram_id,
                                next_tx_data["name"],
                                next_tx_data["difficulty"],
                                next_tx_data["latitude"],
                                next_tx_data["longitude"],
                                next_tx_data["photo_hash"],
                                next_tx_data.get("description", ""),
                                next_tx_data.get("price_wmon", w3.to_wei(1, 'ether'))
                            ).build_transaction({
                                'chainId': 143,
                                'from': pending["wallet_address"],
                                'nonce': nonce,
                                'gas': 500000,
                                'gas_price': await w3.eth.gas_price
                            })
                            await set_pending_wallet(user_id, {
                                "awaiting_tx": True,
                                "tx_data": tx,
                                "wallet_address": pending["wallet_address"],
                                "timestamp": time.time(),
                                "name": next_tx_data["name"],
                                "difficulty": next_tx_data["difficulty"],
                                "latitude": next_tx_data["latitude"],
                                "longitude": next_tx_data["longitude"],
                                "photo_hash": next_tx_data["photo_hash"]
                            })
                            await application.bot.send_message(
                                user_id,
                                f"WMON approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for climb '{next_tx_data['name']}' ({next_tx_data['difficulty']})."
                            )
                            logger.info(f"/submit_tx processed WMON approval, next transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
                            return {"status": "success"}
                        elif next_tx_data["type"] == "purchase_climbing_location":
                            nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                            tx = await contract.functions.purchaseLocation(
                                next_tx_data["location_id"], 0, telegram_id
                            ).build_transaction({
                                'chainId': 143,
                                'from': pending["wallet_address"],
                                'nonce': nonce,
                                'gas': 300000,
                                'gas_price': await w3.eth.gas_price
                            })
                            await set_pending_wallet(user_id, {
                                "awaiting_tx": True,
                                "tx_data": tx,
                                "wallet_address": pending["wallet_address"],
                                "timestamp": time.time()
                            })
                            await application.bot.send_message(
                                user_id,
                                f"WMON approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for purchasing climb #{next_tx_data['location_id']}."
                            )
                            logger.info(f"/submit_tx processed WMON approval, next transaction built for purchase_climb, took {time.time() - start_time:.2f} seconds")
                            return {"status": "success"}
                    await delete_pending_wallet(user_id)
                logger.info(f"/submit_tx confirmed for user {user_id}, took {time.time() - start_time:.2f} seconds")
                return {"status": "success"}
            else:
                # Transaction failed - notify user
                support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
                await application.bot.send_message(
                    user_id,
                    f"Transaction failed or reverted. Check <a href=\"{EXPLORER_URL}/tx/{tx_hash}\">transaction details</a> or contact support at {support_link}. 😅",
                    parse_mode="HTML"
                )
                logger.info(f"/submit_tx failed or pending for user {user_id}, took {time.time() - start_time:.2f} seconds")
                raise HTTPException(status_code=400, detail="Transaction failed or pending")
        except Exception as e:
            logger.error(f"Error verifying transaction for user {user_id}: {str(e)}, took {time.time() - start_time:.2f} seconds")
            error_msg = html.escape(str(e))
            support_link = '<a href="https://t.me/empowertourschat">EmpowerTours Chat</a>'
            await application.bot.send_message(
                user_id,
                f"Error verifying transaction: {error_msg}. Try again or contact support at {support_link}. 😅",
                parse_mode="HTML"
            )
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error in /submit_tx: {str(e)}, took {time.time() - start_time:.2f} seconds")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def webhook(request: Request):
    start_time = time.time()
    try:
        update = await request.json()
        update_id = update.get('update_id')
        logger.info(f"Received webhook update: update_id={update_id}, message_id={update.get('message', {}).get('message_id')}")
        if update_id in processed_updates:
            logger.warning(f"Duplicate update_id {update_id}, skipping")
            return {"status": "duplicate"}
        processed_updates.add(update_id)
        if len(processed_updates) > 1000:
            processed_updates.pop()
        if not application:
            logger.error("Application not initialized, cannot process webhook update")
            raise HTTPException(status_code=500, detail="Application not initialized")
        async with asyncio.timeout(5):
            await application.process_update(Update.de_json(update, application.bot))
        logger.info(f"Processed webhook update, took {time.time() - start_time:.2f} seconds")
        return {"status": "success"}
    except asyncio.TimeoutError:
        logger.error(f"Webhook processing timed out, took {time.time() - start_time:.2f} seconds")
        return {"status": "timeout"}
    except Exception as e:
        logger.error(f"Error in /webhook: {str(e)}, took {time.time() - start_time:.2f} seconds")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
