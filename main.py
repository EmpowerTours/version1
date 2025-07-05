import logging
import os
import signal
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp
from web3 import Web3
import time
from dotenv import load_dotenv
import html
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Mount static files
app.mount("/public", StaticFiles(directory="public"), name="public")

# Global application variable
application = None

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")
CHAT_HANDLE = os.getenv("CHAT_HANDLE")
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
TOURS_TOKEN_ADDRESS = os.getenv("TOURS_TOKEN_ADDRESS")
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS")
LEGACY_ADDRESS = os.getenv("LEGACY_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_CONNECT_PROJECT_ID = os.getenv("WALLET_CONNECT_PROJECT_ID")

# Log environment variables for debugging
logger.info("Environment variables:")
logger.info(f"TELEGRAM_TOKEN: {'Set' if TELEGRAM_TOKEN else 'Missing'}")
logger.info(f"API_BASE_URL: {'Set' if API_BASE_URL else 'Missing'}")
logger.info(f"CHAT_HANDLE: {'Set' if CHAT_HANDLE else 'Missing'}")
logger.info(f"MONAD_RPC_URL: {'Set' if MONAD_RPC_URL else 'Missing'}")
logger.info(f"CONTRACT_ADDRESS: {'Set' if CONTRACT_ADDRESS else 'Missing'}")
logger.info(f"TOURS_TOKEN_ADDRESS: {'Set' if TOURS_TOKEN_ADDRESS else 'Missing'}")
logger.info(f"OWNER_ADDRESS: {'Set' if OWNER_ADDRESS else 'Missing'}")
logger.info(f"LEGACY_ADDRESS: {'Set' if LEGACY_ADDRESS else 'Missing'}")
logger.info(f"PRIVATE_KEY: {'Set' if PRIVATE_KEY else 'Missing'}")
logger.info(f"WALLET_CONNECT_PROJECT_ID: {'Set' if WALLET_CONNECT_PROJECT_ID else 'Missing'}")
missing_vars = []
if not TELEGRAM_TOKEN: missing_vars.append("TELEGRAM_TOKEN")
if not API_BASE_URL: missing_vars.append("API_BASE_URL")
if not CHAT_HANDLE: missing_vars.append("CHAT_HANDLE")
if not MONAD_RPC_URL: missing_vars.append("MONAD_RPC_URL")
if not CONTRACT_ADDRESS: missing_vars.append("CONTRACT_ADDRESS")
if not TOURS_TOKEN_ADDRESS: missing_vars.append("TOURS_TOKEN_ADDRESS")
if not OWNER_ADDRESS: missing_vars.append("OWNER_ADDRESS")
if not LEGACY_ADDRESS: missing_vars.append("LEGACY_ADDRESS")
if not PRIVATE_KEY: missing_vars.append("PRIVATE_KEY")
if not WALLET_CONNECT_PROJECT_ID: missing_vars.append("WALLET_CONNECT_PROJECT_ID")
if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
    logger.warning("Proceeding with limited functionality")
else:
    logger.info("All required environment variables are set")

CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "_toursToken", "type": "address"},
            {"internalType": "address", "name": "_legacyWallet", "type": "address"}
        ],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "inputs": [],
        "name": "InsufficientFee",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "InsufficientTokenBalance",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "InvalidEntryId",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "InvalidLocationId",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "InvalidTournamentId",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "NotParticipant",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "PaymentFailed",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "ProfileExists",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "ProfileRequired",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "TournamentNotActive",
        "type": "error"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "creator", "type": "address"},
            {"indexed": False, "internalType": "string", "name": "name", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "ClimbingLocationCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "entryId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "commenter", "type": "address"},
            {"indexed": False, "internalType": "string", "name": "contentHash", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "CommentAdded",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "entryId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "author", "type": "address"},
            {"indexed": False, "internalType": "string", "name": "contentHash", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "JournalEntryAdded",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "buyer", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "LocationPurchased",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "user", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "ProfileCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "tournamentId", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "entryFee", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "startTime", "type": "uint256"}
        ],
        "name": "TournamentCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "tournamentId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "winner", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "pot", "type": "uint256"}
        ],
        "name": "TournamentEnded",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "tournamentId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "participant", "type": "address"}
        ],
        "name": "TournamentJoined",
        "type": "event"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "entryId", "type": "uint256"},
            {"internalType": "string", "name": "contentHash", "type": "string"}
        ],
        "name": "addComment",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "contentHash", "type": "string"}
        ],
        "name": "addJournalEntry",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "difficulty", "type": "string"},
            {"internalType": "int256", "name": "latitude", "type": "int256"},
            {"internalType": "int256", "name": "longitude", "type": "int256"},
            {"internalType": "string", "name": "photoHash", "type": "string"}
        ],
        "name": "createClimbingLocation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "createProfile",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "entryFee", "type": "uint256"}
        ],
        "name": "createTournament",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tournamentId", "type": "uint256"},
            {"internalType": "address", "name": "winner", "type": "address"}
        ],
        "name": "endTournament",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "locationId", "type": "uint256"}
        ],
        "name": "getClimbingLocation",
        "outputs": [
            {"internalType": "address", "name": "creator", "type": "address"},
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "difficulty", "type": "string"},
            {"internalType": "int256", "name": "latitude", "type": "int256"},
            {"internalType": "int256", "name": "longitude", "type": "int256"},
            {"internalType": "string", "name": "photoHash", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"internalType": "string", "name": "farcasterCastHash", "type": "string"},
            {"internalType": "bool", "name": "isSharedOnFarcaster", "type": "bool"},
            {"internalType": "uint256", "name": "purchaseCount", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getClimbingLocationCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getJournalEntryCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "tournamentId", "type": "uint256"}
        ],
        "name": "joinTournament",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "commentFee",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "profileFee",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "locationId", "type": "uint256"}
        ],
        "name": "purchaseClimbingLocation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "toursToken",
        "outputs": [{"internalType": "contract IERC20", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

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

w3 = None
contract = None
tours_contract = None
pending_wallets = {}
journal_data = {}
build_data = {}
sessions = {}
webhook_failed = False
last_processed_block = 0

def initialize_web3():
    global w3, contract, tours_contract
    if not MONAD_RPC_URL or not CONTRACT_ADDRESS or not TOURS_TOKEN_ADDRESS:
        logger.error("Cannot initialize Web3: missing blockchain-related environment variables")
        return False
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL))
            if w3.is_connected():
                logger.info("Web3 initialized successfully")
                contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
                tours_contract = w3.eth.contract(address=TOURS_TOKEN_ADDRESS, abi=TOURS_ABI)
                logger.info("Contracts initialized successfully")
                return True
            else:
                logger.warning(f"Web3 connection failed on attempt {attempt}/{retries}: not connected")
                if attempt < retries:
                    time.sleep(5)
        except Exception as e:
            logger.error(f"Error initializing Web3 on attempt {attempt}/{retries}: {str(e)}")
            if attempt < retries:
                time.sleep(5)
    logger.error("All Web3 initialization attempts failed. Proceeding without blockchain functionality.")
    w3 = None
    contract = None
    tours_contract = None
    return False

def escape_html(text):
    if not text:
        return ""
    return html.escape(str(text))

async def send_notification(chat_id, message):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        try:
            async with session.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
            ) as response:
                response_data = await response.json()
                if response_data.get("ok"):
                    logger.info(f"Sent notification to chat {chat_id}: {response_data}")
                else:
                    logger.error(f"Failed to send notification to chat {chat_id}: {response_data}")
                return response_data
        except Exception as e:
            logger.error(f"Error in send_notification to chat {chat_id}: {str(e)}")
            return {"ok": False, "error": str(e)}

async def check_webhook():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        try:
            async with session.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo") as response:
                data = await response.json()
                logger.info(f"Webhook info: {data}")
                return data.get("ok") and data.get("result", {}).get("url") == f"{API_BASE_URL.rstrip('/')}/webhook"
        except Exception as e:
            logger.error(f"Error checking webhook: {str(e)}")
            return False

async def reset_webhook():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        try:
            logger.info("Attempting to delete webhook")
            async with session.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook",
                json={"drop_pending_updates": True}
            ) as response:
                delete_data = await response.json()
                logger.info(f"Webhook cleared: {delete_data}")
                if not delete_data.get("ok"):
                    logger.error(f"Failed to delete webhook: {delete_data}")
            logger.info(f"Setting webhook to {API_BASE_URL.rstrip('/')}/webhook")
            async with session.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                json={"url": f"{API_BASE_URL.rstrip('/')}/webhook", "drop_pending_updates": True}
            ) as response:
                set_data = await response.json()
                logger.info(f"Webhook set: {set_data}")
                if not set_data.get("ok"):
                    logger.error(f"Failed to set webhook: {set_data}")
        except Exception as e:
            logger.error(f"Error resetting webhook: {str(e)}")

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start command from user {update.effective_user.id}")
    try:
        await update.message.reply_text(
            "Welcome to EmpowerTours, your rock climbing adventure hub! 🌄\nNew here? Start with /tutorial to set up your wallet and profile.\nReady to climb? Join our community at EmpowerTours Chat https://t.me/empowertourschat 🪨"
        )
    except Exception as e:
        logger.error(f"Error in /start: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /tutorial command from user {update.effective_user.id}")
    try:
        if not CHAT_HANDLE or not MONAD_RPC_URL:
            logger.error("CHAT_HANDLE or MONAD_RPC_URL missing, /tutorial command limited")
            await update.message.reply_text("Tutorial unavailable due to missing configuration (CHAT_HANDLE or MONAD_RPC_URL). Try /help! 😅")
            return
        logger.info("Checking webhook for /tutorial")
        webhook_ok = await check_webhook()
        if not webhook_ok:
            logger.warning("Webhook not set correctly, attempting to reset")
            try:
                await asyncio.wait_for(reset_webhook(), timeout=5)
                logger.info("Webhook reset completed")
            except asyncio.TimeoutError:
                logger.error("Webhook reset timed out")
                await update.message.reply_text(
                    "Webhook setup timed out, but here's the tutorial! 😅\n"
                    "🌟 Tutorial 🌟\n"
                    "1️⃣ Wallet:\n"
                    "- Get MetaMask/Phantom/Gnosis Safe.\n"
                    f"- Add Monad testnet (RPC: {MONAD_RPC_URL}, ID: 10143).\n"
                    "- Get $MON: https://testnet.monad.xyz/faucet\n"
                    "2️⃣ Connect:\n"
                    "- Use /connectwallet to connect via MetaMask/WalletConnect\n"
                    "3️⃣ Profile:\n"
                    "- /createprofile (1 $MON)\n"
                    "4️⃣ Explore:\n"
                    "- /journal [your journal entry]\n"
                    "- /comment [id] [your comment]\n"
                    "- /buildaclimb [name] [difficulty]\n"
                    "- /purchaseclimb [id]\n"
                    "- /findaclimb\n"
                    "- /createtournament [fee]\n"
                    "- /jointournament [id]\n"
                    "- /endtournament [id] [winner]\n"
                    "- /balance\n"
                    "- /help\n"
                    "Join EmpowerTours Chat https://t.me/empowertourschat! Try /connectwallet! 🪨"
                )
                return
        tutorial_text = (
            "🌟 Tutorial 🌟\n"
            "1️⃣ Wallet:\n"
            "- Get MetaMask/Phantom/Gnosis Safe.\n"
            f"- Add Monad testnet (RPC: {MONAD_RPC_URL}, ID: 10143).\n"
            "- Get $MON: https://testnet.monad.xyz/faucet\n"
            "2️⃣ Connect:\n"
            "- Use /connectwallet to connect via MetaMask/WalletConnect\n"
            "3️⃣ Profile:\n"
            "- /createprofile (1 $MON)\n"
            "4️⃣ Explore:\n"
            "- /journal [your journal entry]\n"
            "- /comment [id] [your comment]\n"
            "- /buildaclimb [name] [difficulty]\n"
            "- /purchaseclimb [id]\n"
            "- /findaclimb\n"
            "- /createtournament [fee]\n"
            "- /jointournament [id]\n"
            "- /endtournament [id] [winner]\n"
            "- /balance\n"
            "- /help\n"
            "Join EmpowerTours Chat https://t.me/empowertourschat! Try /connectwallet! 🪨"
        )
        logger.info(f"Sending tutorial response to user {update.effective_user.id}")
        await update.message.reply_text(tutorial_text)
        logger.info(f"Tutorial response sent successfully to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in /tutorial for user {update.effective_user.id}: {str(e)}")
        await update.message.reply_text(f"Error in tutorial: {str(e)}. Try again or use /help! 😅")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /help command from user {update.effective_user.id}")
    try:
        help_text = (
            "🧗 EmpowerTours Commands 🧗\n"
            "/start - Welcome message\n"
            "/tutorial - Setup guide\n"
            "/connectwallet - Connect your wallet\n"
            "/createprofile - Create profile (1 $MON)\n"
            "/journal [entry] - Log a climb (5 $TOURS)\n"
            "/comment [id] [comment] - Comment on a journal (0.1 $MON)\n"
            "/buildaclimb [name] [difficulty] - Create a climb (10 $TOURS)\n"
            "/purchaseclimb [id] - Buy a climb (10 $TOURS)\n"
            "/findaclimb - List climbs\n"
            "/createtournament [fee] - Start a tournament\n"
            "/jointournament [id] - Join a tournament\n"
            "/endtournament [id] [winner] - End a tournament\n"
            "/balance - Check wallet balance\n"
            "Join EmpowerTours Chat https://t.me/empowertourschat! 🪨"
        )
        await update.message.reply_text(help_text)
    except Exception as e:
        logger.error(f"Error in /help: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def connect_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /connectwallet command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /connectwallet command disabled")
        await update.message.reply_text("Wallet connection unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        base_url = API_BASE_URL.rstrip('/')
        connect_url = f"{base_url}/public/connect.html?userId={user_id}"
        logger.info(f"Generated connect URL: {connect_url}")
        keyboard = [[InlineKeyboardButton("Connect with MetaMask/WalletConnect", url=connect_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Click the button to connect your wallet via MetaMask or WalletConnect:",
            reply_markup=reply_markup
        )
        pending_wallets[user_id] = {"awaiting_wallet": True}
    except Exception as e:
        logger.error(f"Error in /connectwallet: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def handle_wallet_address(user_id: str, wallet_address: str, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Handling wallet address for user {user_id}: {wallet_address}")
    if user_id not in pending_wallets or not pending_wallets[user_id].get("awaiting_wallet"):
        logger.warning(f"No pending wallet connection for user {user_id}")
        return
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, wallet connection disabled")
        await context.bot.send_message(user_id, "Wallet connection unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        if w3 and w3.is_address(wallet_address):
            sessions[user_id] = {"wallet_address": wallet_address}
            await context.bot.send_message(user_id, f"Wallet {wallet_address[:6]}... connected! Try /createprofile. 🪙")
            del pending_wallets[user_id]
        else:
            await context.bot.send_message(user_id, "Invalid wallet address. Try /connectwallet again.")
    except Exception as e:
        logger.error(f"Error in handle_wallet_address: {str(e)}")
        await context.bot.send_message(user_id, f"Error: {str(e)}. Try again! 😅")

async def create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /createprofile command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /createprofile command disabled")
        await update.message.reply_text("Profile creation unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        wallet_address = sessions.get(user_id, {}).get("wallet_address")
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            return
        profile_fee = contract.functions.profileFee().call()
        tx = contract.functions.createProfile().build_transaction({
            'from': wallet_address,
            'value': profile_fee,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please send the signed transaction hash for profile creation (1 $MON) using your wallet ({wallet_address})."
        )
        pending_wallets[user_id] = {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": wallet_address
        }
    except Exception as e:
        logger.error(f"Error in /createprofile: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def journal_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /journal command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /journal command disabled")
        await update.message.reply_text("Journal entry unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        content = " ".join(context.args)
        if not content:
            await update.message.reply_text("Use: /journal [your journal entry] Then photo. 📸")
            return
        await update.message.reply_text(f"Great, {update.effective_user.first_name}! Send photo. 🌟")
        journal_data[user_id] = {"content": content, "awaiting_photo": True}
    except Exception as e:
        logger.error(f"Error in /journal: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received photo from user {update.effective_user.id}")
    if not update.message.photo:
        return
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, photo handling disabled")
        await update.message.reply_text("Photo processing unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        if user_id in journal_data and journal_data[user_id].get("awaiting_photo"):
            journal_data[user_id]["photo_id"] = update.message.photo[-1].file_id
            journal_data[user_id]["awaiting_photo"] = False
            wallet_address = sessions.get(user_id, {}).get("wallet_address")
            if not wallet_address:
                await update.message.reply_text("Use /connectwallet! 🪙")
                return
            tx = contract.functions.addJournalEntry(journal_data[user_id]["photo_id"]).build_transaction({
                'from': wallet_address,
                'nonce': w3.eth.get_transaction_count(wallet_address),
                'gas': 200000,
                'gasPrice': w3.eth.gas_price
            })
            await update.message.reply_text(
                f"Please send the signed transaction hash for journal entry (5 $TOURS) using your wallet ({wallet_address})."
            )
            pending_wallets[user_id] = {
                "awaiting_tx": True,
                "tx_data": tx,
                "wallet_address": wallet_address
            }
            del journal_data[user_id]
        elif user_id in build_data and build_data[user_id].get("awaiting_photo"):
            build_data[user_id]["photo_id"] = update.message.photo[-1].file_id
            build_data[user_id]["awaiting_photo"] = False
            build_data[user_id]["awaiting_location"] = True
            await update.message.reply_text(f"Photo received, {update.effective_user.first_name}! Send location. 📍")
    except Exception as e:
        logger.error(f"Error in handle_photo: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def add_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /comment command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /comment command disabled")
        await update.message.reply_text("Commenting unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Use: /comment [id] [your comment] (0.1 $MON) 🗣️")
            return
        entry_id = int(args[0])
        content = " ".join(args[1:])
        wallet_address = sessions.get(user_id, {}).get("wallet_address")
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            return
        comment_fee = contract.functions.commentFee().call()
        tx = contract.functions.addComment(entry_id, content).build_transaction({
            'from': wallet_address,
            'value': comment_fee,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please send the signed transaction hash for comment (0.1 $MON) using your wallet ({wallet_address})."
        )
        pending_wallets[user_id] = {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": wallet_address
        }
    except Exception as e:
        logger.error(f"Error in /comment: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def build_a_climb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /buildaclimb command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /buildaclimb command disabled")
        await update.message.reply_text("Climb creation unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Use: /buildaclimb [name] [difficulty] Then photo, location. 📍")
            return
        name = args[0]
        difficulty = args[1].capitalize()
        await update.message.reply_text(f"Nice, {update.effective_user.first_name}! Send photo. 📸")
        build_data[user_id] = {"name": name, "difficulty": difficulty, "user_id": user_id, "awaiting_photo": True}
    except Exception as e:
        logger.error(f"Error in /buildaclimb: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received location from user {update.effective_user.id}")
    if not update.message.location:
        return
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, location handling disabled")
        await update.message.reply_text("Location processing unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        if user_id not in build_data or not build_data[user_id].get("awaiting_location"):
            return
        latitude = round(update.message.location.latitude * 10**6)
        longitude = round(update.message.location.longitude * 10**6)
        photo_hash = build_data[user_id]["photo_id"]
        wallet_address = sessions.get(user_id, {}).get("wallet_address")
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            return
        tx = contract.functions.createClimbingLocation(
            build_data[user_id]["name"],
            build_data[user_id]["difficulty"],
            latitude,
            longitude,
            photo_hash
        ).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 300000,
            'gasPrice': w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please send the signed transaction hash for climb creation (10 $TOURS) using your wallet ({wallet_address})."
        )
        pending_wallets[user_id] = {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": wallet_address
        }
        del build_data[user_id]
    except Exception as e:
        logger.error(f"Error in handle_location: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def purchase_climb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /purchaseclimb command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /purchaseclimb command disabled")
        await update.message.reply_text("Climb purchase unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Use: /purchaseclimb [id] 🪙")
            return
        location_id = int(args[0])
        wallet_address = sessions.get(user_id, {}).get("wallet_address")
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            return
        tx = contract.functions.purchaseClimbingLocation(location_id).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please send the signed transaction hash for climb purchase (10 $TOURS) using your wallet ({wallet_address})."
        )
        pending_wallets[user_id] = {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": wallet_address
        }
    except Exception as e:
        logger.error(f"Error in /purchaseclimb: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def find_a_climb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /findaclimb command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /findaclimb command disabled")
        await update.message.reply_text("Climb listing unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        if not w3 or not contract:
            await update.message.reply_text("Blockchain connection unavailable. Try again later! 😅")
            return
        count = contract.functions.getClimbingLocationCount().call()
        if count == 0:
            await update.message.reply_text("No climbs found. Create one with /buildaclimb! 🪨")
            return
        climbs = []
        for i in range(count):
            location = contract.functions.getClimbingLocation(i).call()
            climbs.append(
                f"ID: {i}\n"
                f"Name: {location[1]}\n"
                f"Difficulty: {location[2]}\n"
                f"Location: ({location[3] / 10**6}, {location[4] / 10**6})\n"
                f"Creator: {location[0][:6]}...\n"
                f"Purchase Count: {location[10]}\n"
            )
        climb_text = "\n".join(climbs)
        await update.message.reply_text(f"🪨 Available Climbs 🪨\n{climb_text}\nUse /purchaseclimb [id] to buy!")
    except Exception as e:
        logger.error(f"Error in /findaclimb: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def create_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /createtournament command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /createtournament command disabled")
        await update.message.reply_text("Tournament creation unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Use: /createtournament [fee] 🏆")
            return
        entry_fee = int(float(args[0]) * 10**18)
        wallet_address = sessions.get(user_id, {}).get("wallet_address")
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            return
        tx = contract.functions.createTournament(entry_fee).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please send the signed transaction hash for tournament creation using your wallet ({wallet_address})."
        )
        pending_wallets[user_id] = {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": wallet_address
        }
    except Exception as e:
        logger.error(f"Error in /createtournament: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def join_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /jointournament command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /jointournament command disabled")
        await update.message.reply_text("Tournament joining unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Use: /jointournament [id] 🏆")
            return
        tournament_id = int(args[0])
        wallet_address = sessions.get(user_id, {}).get("wallet_address")
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            return
        tx = contract.functions.joinTournament(tournament_id).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please send the signed transaction hash for joining tournament using your wallet ({wallet_address})."
        )
        pending_wallets[user_id] = {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": wallet_address
        }
    except Exception as e:
        logger.error(f"Error in /jointournament: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def end_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /endtournament command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /endtournament command disabled")
        await update.message.reply_text("Tournament ending unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Use: /endtournament [id] [winner] 🏆")
            return
        tournament_id = int(args[0])
        winner_address = args[1]
        wallet_address = sessions.get(user_id, {}).get("wallet_address")
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            return
        if wallet_address.lower() != OWNER_ADDRESS.lower():
            await update.message.reply_text("Only the owner can end tournaments! 😅")
            return
        tx = contract.functions.endTournament(tournament_id, winner_address).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please send the signed transaction hash for ending tournament using your wallet ({wallet_address})."
        )
        pending_wallets[user_id] = {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": wallet_address
        }
    except Exception as e:
        logger.error(f"Error in /endtournament: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /balance command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /balance command disabled")
        await update.message.reply_text("Balance check unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        wallet_address = sessions.get(user_id, {}).get("wallet_address")
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            return
        if not w3 or not tours_contract:
            await update.message.reply_text("Balance check unavailable due to blockchain connection issues. Try again later! 😅")
            return
        balance_wei = w3.eth.get_balance(wallet_address)
        balance_mon = w3.from_wei(balance_wei, 'ether')
        tours_balance = tours_contract.functions.balanceOf(wallet_address).call() / 10**18
        await update.message.reply_text(
            f"💰 Wallet Balance:\n- {balance_mon} $MON\n- {tours_balance:.2f} $TOURS\nAddress: {wallet_address}\nTop up $MON at https://testnet.monad.xyz/faucet! 🪙"
        )
    except Exception as e:
        logger.error(f"Error in /balance: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def handle_tx_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    logger.info(f"Received transaction hash from user {user_id}: {update.message.text}")
    if user_id not in pending_wallets or not pending_wallets[user_id].get("awaiting_tx"):
        logger.warning(f"No pending transaction for user {user_id}")
        return
    tx_hash = update.message.text.strip()
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        await update.message.reply_text("Invalid transaction hash. Send a valid hash (e.g., 0x123...).")
        return
    try:
        if not w3:
            raise Exception("Web3 not available")
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt and receipt.status:
            await update.message.reply_text(f"Transaction confirmed! Tx: {tx_hash} 🪙")
            if CHAT_HANDLE and TELEGRAM_TOKEN:
                message = f"New activity by {escape_html(update.effective_user.username or update.effective_user.first_name)} on EmpowerTours! 🧗 Tx: {escape_html(tx_hash)}"
                await send_notification(CHAT_HANDLE, message)
            del pending_wallets[user_id]
        else:
            await update.message.reply_text("Transaction failed or pending. Check and try again! 😅")
    except Exception as e:
        logger.error(f"Error in handle_tx_hash: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def monitor_events(context: ContextTypes.DEFAULT_TYPE):
    global last_processed_block
    if not w3 or not contract:
        logger.error("Web3 or contract not initialized, cannot monitor events")
        return
    try:
        latest_block = w3.eth.get_block_number()
        if last_processed_block == 0:
            last_processed_block = max(0, latest_block - 100)
        for block_number in range(last_processed_block + 1, latest_block + 1):
            block = w3.eth.get_block(block_number, full_transactions=True)
            for tx in block.transactions:
                receipt = w3.eth.get_transaction_receipt(tx.hash)
                if receipt and receipt.status:
                    for log in receipt.logs:
                        if log.address.lower() == CONTRACT_ADDRESS.lower():
                            try:
                                if log.topics[0].hex() == w3.keccak(text="ProfileCreated(address,uint256)").hex():
                                    event = contract.events.ProfileCreated().process_log(log)
                                    user = event.args.user
                                    message = f"New climber joined EmpowerTours! 🧗 Address: {user[:6]}..."
                                    await send_notification(CHAT_HANDLE, message)
                                elif log.topics[0].hex() == w3.keccak(text="JournalEntryAdded(uint256,address,string,uint256)").hex():
                                    event = contract.events.JournalEntryAdded().process_log(log)
                                    author = event.args.author
                                    entry_id = event.args.entryId
                                    message = f"New journal entry #{entry_id} by {author[:6]}... on EmpowerTours! 📝"
                                    await send_notification(CHAT_HANDLE, message)
                                elif log.topics[0].hex() == w3.keccak(text="CommentAdded(uint256,address,string,uint256)").hex():
                                    event = contract.events.CommentAdded().process_log(log)
                                    commenter = event.args.commenter
                                    entry_id = event.args.entryId
                                    message = f"New comment on journal #{entry_id} by {commenter[:6]}... on EmpowerTours! 🗣️"
                                    await send_notification(CHAT_HANDLE, message)
                                elif log.topics[0].hex() == w3.keccak(text="ClimbingLocationCreated(uint256,address,string,uint256)").hex():
                                    event = contract.events.ClimbingLocationCreated().process_log(log)
                                    creator = event.args.creator
                                    name = event.args.name
                                    message = f"New climb '{name}' created by {creator[:6]}... on EmpowerTours! 🪨"
                                    await send_notification(CHAT_HANDLE, message)
                                elif log.topics[0].hex() == w3.keccak(text="LocationPurchased(uint256,address,uint256)").hex():
                                    event = contract.events.LocationPurchased().process_log(log)
                                    buyer = event.args.buyer
                                    location_id = event.args.locationId
                                    message = f"Climb #{location_id} purchased by {buyer[:6]}... on EmpowerTours! 🪙"
                                    await send_notification(CHAT_HANDLE, message)
                                elif log.topics[0].hex() == w3.keccak(text="TournamentCreated(uint256,uint256,uint256)").hex():
                                    event = contract.events.TournamentCreated().process_log(log)
                                    tournament_id = event.args.tournamentId
                                    entry_fee = event.args.entryFee / 10**18
                                    message = f"New tournament #{tournament_id} created with entry fee {entry_fee} $TOURS on EmpowerTours! 🏆"
                                    await send_notification(CHAT_HANDLE, message)
                                elif log.topics[0].hex() == w3.keccak(text="TournamentJoined(uint256,address)").hex():
                                    event = contract.events.TournamentJoined().process_log(log)
                                    participant = event.args.participant
                                    tournament_id = event.args.tournamentId
                                    message = f"Climber {participant[:6]}... joined tournament #{tournament_id} on EmpowerTours! 🏆"
                                    await send_notification(CHAT_HANDLE, message)
                                elif log.topics[0].hex() == w3.keccak(text="TournamentEnded(uint256,address,uint256)").hex():
                                    event = contract.events.TournamentEnded().process_log(log)
                                    winner = event.args.winner
                                    tournament_id = event.args.tournamentId
                                    pot = event.args.pot / 10**18
                                    message = f"Tournament #{tournament_id} ended! Winner: {winner[:6]}... won {pot} $TOURS on EmpowerTours! 🏆"
                                    await send_notification(CHAT_HANDLE, message)
                            except Exception as e:
                                logger.error(f"Error processing event in block {block_number}: {str(e)}")
        last_processed_block = latest_block
    except Exception as e:
        logger.error(f"Error in monitor_events: {str(e)}")

# Webhook endpoint for wallet connection
@app.post("/submit_wallet")
async def submit_wallet(request: Request):
    global application
    try:
        data = await request.json()
        user_id = data.get("userId")
        wallet_address = data.get("walletAddress")
        if not user_id or not wallet_address:
            logger.error("Missing userId or walletAddress in /submit_wallet")
            raise HTTPException(status_code=400, detail="Missing userId or walletAddress")
        logger.info(f"Received wallet submission for user {user_id}: {wallet_address}")
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN missing, cannot send wallet confirmation")
            raise HTTPException(status_code=500, detail="Bot configuration error")
        if not application:
            logger.error("Application not initialized for /submit_wallet")
            raise HTTPException(status_code=500, detail="Bot not initialized")
        await handle_wallet_address(user_id, wallet_address, application)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in /submit_wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Webhook endpoint for Telegram updates
@app.post("/webhook")
async def webhook(request: Request):
    global application
    try:
        update = await request.json()
        logger.info(f"Received webhook update: {update}")
        if not application:
            logger.error("Application not initialized for webhook")
            raise HTTPException(status_code=500, detail="Bot not initialized")
        await application.update_queue.put(Update.de_json(update, application.bot))
        logger.info("Webhook update processed successfully")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Application setup
async def main():
    global application
    try:
        initialize_web3()
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN missing, cannot start bot")
            return
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        logger.info("Registering command handlers")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("tutorial", tutorial))
        application.add_handler(CommandHandler("help", help))
        application.add_handler(CommandHandler("connectwallet", connect_wallet))
        application.add_handler(CommandHandler("createprofile", create_profile))
        application.add_handler(CommandHandler("journal", journal_entry))
        application.add_handler(CommandHandler("comment", add_comment))
        application.add_handler(CommandHandler("buildaclimb", build_a_climb))
        application.add_handler(CommandHandler("purchaseclimb", purchase_climb))
        application.add_handler(CommandHandler("findaclimb", find_a_climb))
        application.add_handler(CommandHandler("createtournament", create_tournament))
        application.add_handler(CommandHandler("jointournament", join_tournament))
        application.add_handler(CommandHandler("endtournament", end_tournament))
        application.add_handler(CommandHandler("balance", balance))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.LOCATION, handle_location))
        application.add_handler(MessageHandler(filters.Regex(r'^0x[a-fA-F0-9]{64}$'), handle_tx_hash))
        logger.info("Command handlers registered successfully")

        # Periodic event monitoring
        application.job_queue.run_repeating(monitor_events, interval=10, first=0)

        # Force webhook reset
        logger.info("Forcing webhook reset on startup")
        await reset_webhook()
        await application.initialize()
        await application.start()
        await application.updater.start_webhook(
            listen="0.0.0.0",
            port=8080,
            url_path="/webhook",
            webhook_url=f"{API_BASE_URL.rstrip('/')}/webhook"
        )
        logger.info("Bot started successfully")

        # Keep application running
        while True:
            await asyncio.sleep(3600)
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

# Signal handler for graceful shutdown
def handle_shutdown(signum, frame):
    logger.info("Received shutdown signal")
    raise SystemExit

# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

if __name__ == "__main__":
    try:
        uvicorn.run(app, host="0.0.0.0", port=8080)
    except SystemExit:
        logger.info("Shutting down bot")
    except Exception as e:
        logger.error(f"Error running Uvicorn: {str(e)}")
