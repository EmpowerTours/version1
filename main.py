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
        "inputs": [{"internalType": "string", "name": "contentHash", "type": "string"}],
        "name": "addJournalEntry",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
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
        "inputs": [{"internalType": "uint256", "name": "entryFee", "type": "uint256"}],
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
        "inputs": [],
        "name": "getClimbingLocationCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tournamentId", "type": "uint256"}],
        "name": "joinTournament",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "locationId", "type": "uint256"}],
        "name": "purchaseClimbingLocation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "name": "climbingLocations",
        "outputs": [
            {"internalType": "address", "name": "creator", "type": "address"},
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "difficulty", "type": "string"},
            {"internalType": "int256", "name": "latitude", "type": "int256"},
            {"internalType": "int256", "name": "longitude", "type": "int256"},
            {"internalType": "string", "name": "photoHash", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "locationCreationCost",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "profiles",
        "outputs": [
            {"internalType": "bool", "name": "exists", "type": "bool"},
            {"internalType": "uint256", "name": "journalCount", "type": "uint256"}
        ],
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
        "inputs": [],
        "name": "commentFee",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
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

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start command from user {update.effective_user.id}")
    if not CHAT_HANDLE:
        logger.error("CHAT_HANDLE missing, /start command limited")
        await update.message.reply_text(
            "Welcome to EmpowerTours, your rock climbing adventure hub! 🌄\nNew here? Start with /tutorial to set up your wallet and profile."
        )
        return
    await update.message.reply_text(
        f"Welcome to EmpowerTours, your rock climbing adventure hub! 🌄\nNew here? Start with /tutorial to set up your wallet and profile.\nReady to climb? Join our community at EmpowerTours Chat[](https://t.me/empowertourschat)! 🪨",
        parse_mode="HTML"
    )

async def tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /tutorial command from user {update.effective_user.id}")
    if not CHAT_HANDLE or not MONAD_RPC_URL:
        logger.error("CHAT_HANDLE or MONAD_RPC_URL missing, /tutorial command limited")
        await update.message.reply_text("Tutorial unavailable due to configuration issues. Try /help! 😅")
        return
    tutorial_text = (
        f"🌟 <b>Tutorial</b> 🌟\n"
        "1️⃣ <b>Wallet</b>:\n"
        "- Get MetaMask/Phantom/Gnosis Safe.\n"
        f"- Add Monad testnet (RPC: {escape_html(MONAD_RPC_URL)}, ID: 10143).\n"
        "- Get $MON: <a href=\"https://testnet.monad.xyz/faucet\">Faucet</a>\n"
        "2️⃣ <b>Connect</b>:\n"
        "- Use /connectwallet to connect via MetaMask/WalletConnect\n"
        "3️⃣ <b>Profile</b>:\n"
        "- /createprofile (1 $MON)\n"
        "4️⃣ <b>Explore</b>:\n"
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
        f"Join <a href=\"https://t.me/empowertourschat\">{escape_html(CHAT_HANDLE)}</a>! Try /connectwallet! 🪨"
    )
    await update.message.reply_text(tutorial_text, parse_mode="HTML")

async def connect_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /connectwallet command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /connectwallet command disabled")
        await update.message.reply_text("Wallet connection unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        user_id = str(update.effective_user.id)
        # Ensure no double slashes in URL
        base_url = API_BASE_URL.rstrip('/')
        connect_url = f"{base_url}/public/connect.html?userId={user_id}"
        logger.info(f"Generated connect URL: {connect_url}")
        keyboard = [[InlineKeyboardButton("Connect with MetaMask/WalletConnect", url=connect_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Click the button to connect your wallet via MetaMask or WalletConnect:",
            reply_markup=reply_markup,
            parse_mode="HTML"
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
        payment_tx = {
            'to': OWNER_ADDRESS,
            'value': w3.to_wei(1, 'ether'),
            'nonce': w3.eth.get_transaction_count(wallet_address) + 1,
            'gas': 21000,
            'gasPrice': w3.eth.gas_price
        }
        await update.message.reply_text(
            f"Please send the signed transaction hash for profile creation using your wallet ({wallet_address})."
        )
        pending_wallets[user_id] = {
            "awaiting_tx": True,
            "tx_data": tx,
            "next_tx": {"tx_data": payment_tx},
            "wallet_address": wallet_address
        }
    except Exception as e:
        logger.error(f"Error in /createprofile: {str(e)}")
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
            if pending_wallets[user_id].get("next_tx"):
                await update.message.reply_text(
                    "Profile creation transaction confirmed! Please send the signed transaction hash for the payment (1 $MON to owner) using your wallet."
                )
                pending_wallets[user_id] = {
                    "awaiting_tx": True,
                    "tx_data": pending_wallets[user_id]["next_tx"]["tx_data"],
                    "wallet_address": pending_wallets[user_id]["wallet_address"]
                }
            else:
                await update.message.reply_text(f"Profile created successfully! Tx: {tx_hash} 🪙")
                if CHAT_HANDLE and TELEGRAM_TOKEN:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id": CHAT_HANDLE,
                                "text": f"New climber {escape_html(update.effective_user.username or update.effective_user.first_name)} joined EmpowerTours! 🧗 Tx: {escape_html(tx_hash)}",
                                "parse_mode": "HTML"
                            }
                        ) as response:
                            logger.info("Sent profile creation notification to chat")
                del pending_wallets[user_id]
        else:
            await update.message.reply_text("Transaction failed or pending. Check and try again! 😅")
    except Exception as e:
        logger.error(f"Error in handle_tx_hash: {str(e)}")
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
            f"💰 Wallet Balance:\n- {balance_mon} $MON\n- {tours_balance:.2f} $TOURS\nAddress: {wallet_address}\nTop up $MON at <a href=\"https://testnet.monad.xyz/faucet\">Faucet</a>! 🪙",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in /balance: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def find_a_climb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /findaclimb command from user {update.effective_user.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /findaclimb command disabled")
        await update.message.reply_text("Climb discovery unavailable due to configuration issues. Try again later! 😅")
        return
    try:
        if not w3 or not contract:
            await update.message.reply_text("Climb discovery unavailable due to blockchain connection issues. Try again later! 😅")
            return
        count = contract.functions.getClimbingLocationCount().call()
        locations = []
        for i in range(count):
            loc = contract.functions.climbingLocations(i).call()
            locations.append(
                f"ID: {i}, Name: {escape_html(loc[1])}, Difficulty: {escape_html(loc[2])}, Location: ({loc[3]/10**6:.4f}, {loc[4]/10**6:.4f})"
            )
        if not locations:
            await update.message.reply_text("No climbs yet! Create one with /buildaclimb 🪨")
        else:
            await update.message.reply_text(
                f"Discover Climbs:\n{'\n'.join(locations)}\nCreate your own with /buildaclimb or buy one with /purchaseclimb! 🌄",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error in /findaclimb: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /help command from user {update.effective_user.id}")
    if not CHAT_HANDLE:
        logger.error("CHAT_HANDLE missing, /help command limited")
        await update.message.reply_text(
            "🏔️ Commands 🧗‍♀️\n"
            "/start - Begin\n"
            "/tutorial - Guide\n"
            "/connectwallet - Connect wallet\n"
            "/createprofile - Join (1 $MON)\n"
            "/journal [your journal entry] - Log climb\n"
            "/comment [id] [your comment] - Comment (0.1 $MON)\n"
            "/buildaclimb [name] [difficulty] - Create climb\n"
            "/purchaseclimb [id] - Buy climb\n"
            "/findaclimb - Explore climbs\n"
            "/createtournament [fee] - Start tournament\n"
            "/jointournament [id] - Join tournament\n"
            "/endtournament [id] [winner] - End tournament\n"
            "/balance - Check balance\n"
            "/help - Menu"
        )
        return
    await update.message.reply_text(
        f"🏔️ Commands 🧗‍♀️\n"
        "<b>/start</b> - Begin\n"
        "<b>/tutorial</b> - Guide\n"
        "<b>/connectwallet</b> - Connect wallet\n"
        "<b>/createprofile</b> - Join (1 $MON)\n"
        "<b>/journal [your journal entry]</b> - Log climb\n"
        "<b>/comment [id] [your comment]</b> - Comment (0.1 $MON)\n"
        "<b>/buildaclimb [name] [difficulty]</b> - Create climb\n"
        "<b>/purchaseclimb [id]</b> - Buy climb\n"
        "<b>/findaclimb</b> - Explore climbs\n"
        "<b>/createtournament [fee]</b> - Start tournament\n"
        "<b>/jointournament [id]</b> - Join tournament\n"
        "<b>/endtournament [id] [winner]</b> - End tournament\n"
        "<b>/balance</b> - Check balance\n"
        "<b>/help</b> - Menu\n"
        f"Join <a href=\"https://t.me/empowertourschat\">{escape_html(CHAT_HANDLE)}</a>! 🌄",
        parse_mode="HTML"
    )

async def monitor_events(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not w3 or not contract or not CHAT_HANDLE or not TELEGRAM_TOKEN:
            logger.error("Event monitoring skipped due to Web3, contract, or environment variable unavailability")
            return
        latest_block = w3.eth.get_block_number()
        event_filter = contract.events.ClimbingLocationCreated.create_filter(from_block=latest_block-10, to_block=latest_block)
        events = event_filter.get_all_entries()
        for event in events:
            location_id = event["args"]["locationId"]
            creator = event["args"]["creator"] or ""
            name = escape_html(event["args"]["name"] or "")
            tx_hash = escape_html(event["transactionHash"].hex() or "")
            location = contract.functions.climbingLocations(location_id).call()
            message = (
                f"New climb by {escape_html(creator[:6])}...! 🧗\n"
                f"Name: {name}\n"
                f"Location: ({int(location[3] or 0)/10**6:.4f}, {int(location[4] or 0)/10**6:.4f})\n"
                f"Tx: {tx_hash}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id": CHAT_HANDLE,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                ) as response:
                    logger.info(f"Sent climb notification to chat: {await response.json()}")
    except Exception as e:
        logger.error(f"Error in monitor_events: {str(e)}")

# API Endpoints
@app.get("/sessions/{user_id}")
async def get_session(user_id: str):
    logger.info(f"Fetching session for user {user_id}")
    session = sessions.get(user_id, {})
    return {"wallet_address": session.get("wallet_address")}

@app.post("/wallet")
async def connect_wallet_endpoint(request: Request):
    logger.info("Received /wallet request")
    data = await request.json()
    user_id = data.get("telegramUserId")
    wallet_address = data.get("walletAddress")
    if not user_id or not wallet_address:
        logger.error("Missing userId or walletAddress in /wallet request")
        raise HTTPException(status_code=400, detail="Missing userId or walletAddress")
    try:
        bot_app = app.state.bot_application
        await handle_wallet_address(user_id, wallet_address, bot_app)
        logger.info(f"Wallet connected for user {user_id}: {wallet_address}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in /wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_profile")
async def create_profile_endpoint(request: Request):
    logger.info("Received /create_profile request")
    data = await request.json()
    wallet_address = data.get("wallet_address")
    user_id = data.get("user_id")
    username = data.get("username")
    if not wallet_address or not user_id:
        logger.error("Missing wallet_address or user_id in /create_profile request")
        raise HTTPException(status_code=400, detail="Missing wallet_address or user_id")
    try:
        profile_fee = contract.functions.profileFee().call()
        tx = contract.functions.createProfile().build_transaction({
            'from': wallet_address,
            'value': profile_fee,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        payment_tx = {
            'to': OWNER_ADDRESS,
            'value': w3.to_wei(1, 'ether'),
            'nonce': w3.eth.get_transaction_count(wallet_address) + 1,
            'gas': 21000,
            'gasPrice': w3.eth.gas_price
        }
        logger.info(f"Profile creation transaction prepared for user {user_id}")
        return {"status": "success", "tx_data": tx, "next_tx": {"tx_data": payment_tx}}
    except Exception as e:
        logger.error(f"Error in /create_profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/journal_entry")
async def journal_entry_endpoint(request: Request):
    logger.info("Received /journal_entry request")
    data = await request.json()
    wallet_address = data.get("wallet_address")
    content = data.get("content")
    user_id = data.get("user_id")
    if not wallet_address or not content or not user_id:
        logger.error("Missing wallet_address, content, or user_id in /journal_entry request")
        raise HTTPException(status_code=400, detail="Missing wallet_address, content, or user_id")
    try:
        tx = contract.functions.addJournalEntry(content).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"Journal entry transaction prepared for user {user_id}")
        return {"status": "success", "tx_data": tx}
    except Exception as e:
        logger.error(f"Error in /journal_entry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_comment")
async def add_comment_endpoint(request: Request):
    logger.info("Received /add_comment request")
    data = await request.json()
    wallet_address = data.get("wallet_address")
    entry_id = data.get("entry_id")
    content = data.get("content")
    user_id = data.get("user_id")
    if not wallet_address or not entry_id or not content or not user_id:
        logger.error("Missing wallet_address, entry_id, content, or user_id in /add_comment request")
        raise HTTPException(status_code=400, detail="Missing wallet_address, entry_id, content, or user_id")
    try:
        comment_fee = contract.functions.commentFee().call()
        tx = contract.functions.addComment(entry_id, content).build_transaction({
            'from': wallet_address,
            'value': comment_fee,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"Comment transaction prepared for user {user_id}")
        return {"status": "success", "tx_data": tx}
    except Exception as e:
        logger.error(f"Error in /add_comment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_climbing_location")
async def create_climbing_location_endpoint(request: Request):
    logger.info("Received /create_climbing_location request")
    data = await request.json()
    wallet_address = data.get("wallet_address")
    name = data.get("name")
    difficulty = data.get("difficulty")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    photo_hash = data.get("photo_hash")
    user_id = data.get("user_id")
    if not all([wallet_address, name, difficulty, latitude, longitude, photo_hash, user_id]):
        logger.error("Missing required fields in /create_climbing_location request")
        raise HTTPException(status_code=400, detail="Missing required fields")
    try:
        tx = contract.functions.createClimbingLocation(name, difficulty, latitude, longitude, photo_hash).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 300000,
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"Climb creation transaction prepared for user {user_id}")
        return {"status": "success", "tx_data": tx}
    except Exception as e:
        logger.error(f"Error in /create_climbing_location: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/purchase_climb")
async def purchase_climb_endpoint(request: Request):
    logger.info("Received /purchase_climb request")
    data = await request.json()
    wallet_address = data.get("wallet_address")
    location_id = data.get("location_id")
    user_id = data.get("user_id")
    if not wallet_address or not location_id or not user_id:
        logger.error("Missing wallet_address, location_id, or user_id in /purchase_climb request")
        raise HTTPException(status_code=400, detail="Missing wallet_address, location_id, or user_id")
    try:
        tx = contract.functions.purchaseClimbingLocation(location_id).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"Climb purchase transaction prepared for user {user_id}")
        return {"status": "success", "tx_data": tx}
    except Exception as e:
        logger.error(f"Error in /purchase_climb: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_tournament")
async def create_tournament_endpoint(request: Request):
    logger.info("Received /create_tournament request")
    data = await request.json()
    wallet_address = data.get("wallet_address")
    entry_fee = data.get("entry_fee")
    user_id = data.get("user_id")
    if not wallet_address or not entry_fee or not user_id:
        logger.error("Missing wallet_address, entry_fee, or user_id in /create_tournament request")
        raise HTTPException(status_code=400, detail="Missing wallet_address, entry_fee, or user_id")
    try:
        tx = contract.functions.createTournament(entry_fee).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"Tournament creation transaction prepared for user {user_id}")
        return {"status": "success", "tx_data": tx}
    except Exception as e:
        logger.error(f"Error in /create_tournament: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/join_tournament")
async def join_tournament_endpoint(request: Request):
    logger.info("Received /join_tournament request")
    data = await request.json()
    wallet_address = data.get("wallet_address")
    tournament_id = data.get("tournament_id")
    user_id = data.get("user_id")
    if not wallet_address or not tournament_id or not user_id:
        logger.error("Missing wallet_address, tournament_id, or user_id in /join_tournament request")
        raise HTTPException(status_code=400, detail="Missing wallet_address, tournament_id, or user_id")
    try:
        tx = contract.functions.joinTournament(tournament_id).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"Tournament join transaction prepared for user {user_id}")
        return {"status": "success", "tx_data": tx}
    except Exception as e:
        logger.error(f"Error in /join_tournament: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/end_tournament")
async def end_tournament_endpoint(request: Request):
    logger.info("Received /end_tournament request")
    data = await request.json()
    wallet_address = data.get("wallet_address")
    tournament_id = data.get("tournament_id")
    winner_address = data.get("winner_address")
    user_id = data.get("user_id")
    if not wallet_address or not tournament_id or not winner_address or not user_id:
        logger.error("Missing wallet_address, tournament_id, winner_address, or user_id in /end_tournament request")
        raise HTTPException(status_code=400, detail="Missing wallet_address, tournament_id, winner_address, or user_id")
    try:
        tx = contract.functions.endTournament(tournament_id, winner_address).build_transaction({
            'from': wallet_address,
            'nonce': w3.eth.get_transaction_count(wallet_address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"Tournament end transaction prepared for user {user_id}")
        return {"status": "success", "tx_data": tx}
    except Exception as e:
        logger.error(f"Error in /end_tournament: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Webhook Endpoint
@app.post("/webhook")
async def webhook(request: Request):
    logger.info("Received webhook request")
    try:
        update = Update.de_json(await request.json(), app.state.bot_application.bot)
        if update:
            logger.info(f"Processing update: {update.update_id}")
            await app.state.bot_application.process_update(update)
            logger.info(f"Update {update.update_id} processed successfully")
            return {"status": "ok"}
        else:
            logger.warning("Invalid update received")
            raise HTTPException(status_code=400, detail="Invalid update")
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        global webhook_failed
        webhook_failed = True
        raise HTTPException(status_code=500, detail=str(e))

# Initialize Telegram Bot
async def init_bot():
    try:
        logger.info("Initializing Telegram bot...")
        bot_app = Application.builder().token(TELEGRAM_TOKEN or "").build()
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CommandHandler("tutorial", tutorial))
        bot_app.add_handler(CommandHandler("connectwallet", connect_wallet))
        bot_app.add_handler(CommandHandler("createprofile", create_profile))
        bot_app.add_handler(CommandHandler("journal", journal_entry))
        bot_app.add_handler(CommandHandler("comment", add_comment))
        bot_app.add_handler(CommandHandler("buildaclimb", build_a_climb))
        bot_app.add_handler(CommandHandler("purchaseclimb", purchase_climb))
        bot_app.add_handler(CommandHandler("findaclimb", find_a_climb))
        bot_app.add_handler(CommandHandler("createtournament", create_tournament))
        bot_app.add_handler(CommandHandler("jointournament", join_tournament))
        bot_app.add_handler(CommandHandler("endtournament", end_tournament))
        bot_app.add_handler(CommandHandler("balance", balance))
        bot_app.add_handler(CommandHandler("help", help))
        bot_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        bot_app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tx_hash))
        bot_app.job_queue.run_repeating(monitor_events, interval=30)
        app.state.bot_application = bot_app
        await bot_app.initialize()
        await bot_app.start()
        logger.info("Telegram bot initialized")
        if webhook_failed:
            logger.warning("Webhook failed, starting polling as fallback")
            await bot_app.updater.start_polling(drop_pending_updates=True, poll_interval=1.0, timeout=10)
    except Exception as e:
        logger.error(f"Error initializing bot: {str(e)}")
        raise

# Startup and Shutdown
@app.on_event("startup")
async def startup_event():
    logger.info("Starting application...")
    initialize_web3()
    await init_bot()
    if TELEGRAM_TOKEN and API_BASE_URL:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook",
                json={"drop_pending_updates": True}
            ) as response:
                logger.info(f"Webhook cleared: {await response.json()}")
            async with session.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                json={"url": f"{API_BASE_URL}/webhook"}
            ) as response:
                logger.info(f"Webhook set: {await response.json()}")
    else:
        logger.error("TELEGRAM_TOKEN or API_BASE_URL missing, webhook not set")
        global webhook_failed
        webhook_failed = True

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down application...")
    if hasattr(app.state, "bot_application"):
        await app.state.bot_application.updater.stop()
        await app.state.bot_application.stop()
        await app.state.bot_application.shutdown()
        logger.info("Telegram bot shutdown complete")

# Signal Handling
def handle_shutdown(signum, frame):
    logger.info("Received shutdown signal, stopping application...")
    if hasattr(app.state, "bot_application"):
        asyncio.create_task(app.state.bot_application.updater.stop())
        asyncio.create_task(app.state.bot_application.stop
