import os
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filtersimport os
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from web3 import Web3
from dotenv import load_dotenv
from eth_account import Account

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
TOURS_TOKEN_ADDRESS = os.getenv("TOURS_TOKEN_ADDRESS")
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS")
LEGACY_ADDRESS = os.getenv("LEGACY_ADDRESS")
CHAT_HANDLE = "@empowertourschat"  # Telegram group handle

# Connect to Monad testnet
w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL))
account = Account.from_key(PRIVATE_KEY)

# EmpowerTours contract ABI
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
            {"indexed": True, "internalType": "address", "name": "previousOwner", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "newOwner", "type": "address"}
        ],
        "name": "OwnershipTransferred",
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
            {"internalType": "string", "name": "contentHash", "type": "string"}
        ],
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
        "inputs": [],
        "name": "getClimbingLocationCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "entryId", "type": "uint256"}
        ],
        "name": "getCommentCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getJournalEntryCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getTournamentCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
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
        "inputs": [
            {"internalType": "uint256", "name": "locationId", "type": "uint256"}
        ],
        "name": "purchaseClimbingLocation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
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
        "name": "commentFee",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "journalComments",
        "outputs": [
            {"internalType": "address", "name": "commenter", "type": "address"},
            {"internalType": "string", "name": "contentHash", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "journalEntries",
        "outputs": [
            {"internalType": "address", "name": "author", "type": "address"},
            {"internalType": "string", "name": "contentHash", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "journalReward",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "legacyWallet",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "locationCreationCost",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
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
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "renounceOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "tournaments",
        "outputs": [
            {"internalType": "uint256", "name": "entryFee", "type": "uint256"},
            {"internalType": "uint256", "name": "totalPot", "type": "uint256"},
            {"internalType": "address", "name": "winner", "type": "address"},
            {"internalType": "bool", "name": "isActive", "type": "bool"},
            {"internalType": "uint256", "name": "startTime", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "toursToken",
        "outputs": [
            {"internalType": "contract IERC20", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "newOwner", "type": "address"}
        ],
        "name": "transferOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# ToursToken ABI
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
    }
]

# Initialize contracts
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
tours_contract = w3.eth.contract(address=TOURS_TOKEN_ADDRESS, abi=TOURS_ABI)

# Ensure Web3 connection
if not w3.is_connected():
    logger.error("Failed to connect to Monad testnet")
    raise ConnectionError("Cannot connect to Monad testnet")

# Helper function to get message or edited_message
def get_message(update):
    if update.message:
        return update.message, "message"
    elif update.edited_message:
        return update.edited_message, "edited_message"
    return None, None

# Helper function to get dynamic gas fees
def get_gas_fees():
    try:
        base_fee = w3.eth.get_block('latest')['baseFeePerGas']
        max_priority_fee = w3.eth.max_priority_fee
        max_fee_per_gas = base_fee + max_priority_fee
        return {
            'maxFeePerGas': max_fee_per_gas,
            'maxPriorityFeePerGas': max_priority_fee
        }
    except Exception as e:
        logger.error(f"Error fetching gas fees: {str(e)}")
        return {
            'maxFeePerGas': w3.to_wei('2', 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei('1', 'gwei')
        }

async def start(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /start in the chat to begin! 🧗"
            )
        return
    await message.reply_text(
        "Welcome to EmpowerTours, your rock climbing adventure hub! 🌄\n"
        "New here? Start with /tutorial to set up your Monad wallet and profile.\n"
        "Ready to climb? Join our community at https://t.me/empowertourschat! 🪨"
    )

async def tutorial(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /tutorial in the chat to learn how to start! 🧗"
            )
        return

    tutorial_text = (
        "🌟 Welcome to EmpowerTours Tutorial! 🌟\n\n"
        "Let's get you climbing on the Monad blockchain! Follow these steps:\n\n"
        "1️⃣ **Create a Monad Wallet**:\n"
        "   - Download a wallet like MetaMask[](https://metamask.io).\n"
        "   - Set up a new wallet and securely save your seed phrase.\n"
        "   - Add the Monad testnet to MetaMask:\n"
        "     - Network Name: Monad Testnet\n"
        "     - RPC URL: https://testnet-rpc.monad.xyz\n"
        "     - Chain ID: 10143\n"
        "     - Currency: MON\n"
        "   - Get testnet $MON from the faucet: https://testnet.monad.xyz/faucet\n\n"
        "2️⃣ **Create Your Profile**:\n"
        "   - Use /createprofile <your_wallet_address> (e.g., /createprofile 0x123...).\n"
        "   - Send 1 $MON to join the EmpowerTours community!\n\n"
        "3️⃣ **Explore the App**:\n"
        "   - /journal <description>: Log your climbs and earn $TOURS (send a photo after).\n"
        "   - /buildaclimb <name> <difficulty>: Create a climbing location (10 $TOURS).\n"
        "   - /purchaseclimb <location_id>: Buy access to climbs.\n"
        "   - /createtournament <entry_fee>: Start a tournament to win big!\n"
        "   - /findaclimb: Discover climbing spots worldwide.\n"
        "   - /help: See all commands.\n\n"
        "4️⃣ **Join the Community**:\n"
        "   - Chat with climbers at https://t.me/empowertourschat.\n"
        "   - Share your adventures and compete in tournaments!\n\n"
        "Need help? Just ask! Ready to start? Try /createprofile now! 🪨✨"
    )
    await message.reply_text(tutorial_text)

async def create_profile(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /createprofile in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text(
                "Please provide your wallet address, e.g., /createprofile 0xYourAddress 🪙"
            )
            return
        wallet_address = context.args[0]
        if not w3.is_address(wallet_address):
            await message.reply_text("Invalid wallet address! Use a valid Monad address. 😕")
            return

        profile_fee = contract.functions.profileFee().call()
        balance = w3.eth.get_balance(account.address)
        gas_estimate = contract.functions.createProfile().estimate_gas({
            'from': account.address,
            'value': profile_fee
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        gas_cost = gas_limit * gas_fees['maxFeePerGas']

        if balance < gas_cost + profile_fee:
            await message.reply_text(
                f"Oops! Need {w3.from_wei(profile_fee + gas_cost, 'ether')} $MON for profile creation. "
                f"Your balance: {w3.from_wei(balance, 'ether')} $MON. "
                "Top up at https://testnet.monad.xyz/faucet! 🪙"
            )
            return

        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.createProfile().build_transaction({
            'chainId': 10143,
            'from': account.address,
            'value': profile_fee,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            context.user_data['wallet_address'] = wallet_address
            await message.reply_text(
                f"Welcome aboard, {user.first_name}! Your profile is live! 🎉 Tx: {tx_hash.hex()}\n"
                "Try /journal to log your first climb or /buildaclimb to share a spot! 🪨"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=f"New climber {user.username} joined EmpowerTours! 🧗 Tx: {tx_hash.hex()}"
            )
        else:
            await message.reply_text("Transaction failed. Try again, you got this! 💪")
    except Exception as e:
        logger.error(f"Error in /createprofile: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def journal_entry(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /journal in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text(
                "Share your climb story, e.g., /journal Conquered Mt. Monad! Then send a photo. 📸"
            )
            return
        content = " ".join(context.args)
        content_hash = w3.keccak(text=content).hex()

        context.user_data['journal'] = {
            'user_id': user.id,
            'username': user.username,
            'content_hash': content_hash,
            'awaiting_photo': True
        }
        await message.reply_text(
            f"Awesome story, {user.first_name}! Send a photo to complete your journal entry. 🌟"
        )
    except Exception as e:
        logger.error(f"Error in /journal: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def handle_journal_photo(update: Update, context):
    message, update_type = get_message(update)
    if message is None or not message.photo:
        return

    try:
        user = message.from_user
        journal_data = context.user_data.get('journal')
        if not journal_data or not journal_data.get('awaiting_photo'):
            return

        photo_id = message.photo[-1].file_id
        journal_data['photo_id'] = photo_id
        journal_data['awaiting_photo'] = False

        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        gas_estimate = contract.functions.addJournalEntry(journal_data['content_hash']).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.addJournalEntry(journal_data['content_hash']).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Journal entry logged, {user.first_name}! You earned 5 $TOURS! 🎉 Tx: {tx_hash.hex()}"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=f"{user.username} shared a climb journal! 🪨 Check it out! Tx: {tx_hash.hex()}"
            )
            context.user_data.pop('journal', None)
        else:
            await message.reply_text("Transaction failed. Try again, climber! 💪")
    except Exception as e:
        logger.error(f"Error in handle_journal_photo: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def add_comment(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /comment in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if len(context.args) < 2:
            await message.reply_text(
                "Add a comment, e.g., /comment 1 Epic climb! (Costs 0.1 $MON) 🗣️"
            )
            return
        entry_id = int(context.args[0])
        comment = " ".join(context.args[1:])
        comment_hash = w3.keccak(text=comment).hex()
        comment_fee = contract.functions.commentFee().call()

        balance = w3.eth.get_balance(account.address)
        gas_estimate = contract.functions.addComment(entry_id, comment_hash).estimate_gas({
            'from': account.address,
            'value': comment_fee
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        gas_cost = gas_limit * gas_fees['maxFeePerGas']

        if balance < gas_cost + comment_fee:
            await message.reply_text(
                f"Need {w3.from_wei(comment_fee + gas_cost, 'ether')} $MON to comment. "
                "Top up at https://testnet.monad.xyz/faucet! 🪙"
            )
            return

        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.addComment(entry_id, comment_hash).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'value': comment_fee,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Comment added to entry #{entry_id}, {user.first_name}! 🎉 Tx: {tx_hash.hex()}"
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /comment: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def build_a_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /buildaclimb in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if len(context.args) < 2:
            await message.reply_text(
                "Share a climb spot, e.g., /buildaclimb EpicPeak Hard. Then send a photo and location. 📍"
            )
            return
        name = context.args[0]
        difficulty = context.args[1].capitalize()

        context.user_data['buildaclimb'] = {
            'name': name,
            'difficulty': difficulty,
            'user_id': user.id,
            'username': user.username,
            'awaiting_photo': True
        }
        await message.reply_text(
            f"Nice one, {user.first_name}! Send a photo of the climbing spot. 📸"
        )
    except Exception as e:
        logger.error(f"Error in /buildaclimb: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def handle_photo(update: Update, context):
    message, update_type = get_message(update)
    if message is None or not message.photo:
        return

    try:
        user = message.from_user
        build_data = context.user_data.get('buildaclimb')
        journal_data = context.user_data.get('journal')
        if build_data and build_data.get('awaiting_photo'):
            photo_id = message.photo[-1].file_id
            build_data['photo_id'] = photo_id
            build_data['awaiting_photo'] = False
            build_data['awaiting_location'] = True
            await message.reply_text(
                f"Photo received, {user.first_name}! Now share the location of the climb. 📍"
            )
        elif journal_data and journal_data.get('awaiting_photo'):
            await handle_journal_photo(update, context)
    except Exception as e:
        logger.error(f"Error in handle_photo: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def handle_location(update: Update, context):
    message, update_type = get_message(update)
    if message is None or not message.location:
        return

    try:
        user = message.from_user
        build_data = context.user_data.get('buildaclimb')
        if not build_data or not build_data.get('awaiting_location'):
            return

        latitude = int(message.location.latitude * 10**6)
        longitude = int(message.location.longitude * 10**6)
        photo_hash = build_data['photo_id']

        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        gas_estimate = contract.functions.createClimbingLocation(
            build_data['name'], build_data['difficulty'], latitude, longitude, photo_hash
        ).estimate_gas({'from': account.address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)

        # Approve $TOURS spending
        location_cost = contract.functions.locationCreationCost().call()
        approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, location_cost).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_approve = w3.eth.account.sign_transaction(approve_tx, PRIVATE_KEY)
        approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
        w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)

        # Create climbing location
        tx = contract.functions.createClimbingLocation(
            build_data['name'], build_data['difficulty'], latitude, longitude, photo_hash
        ).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce + 1,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            location_id = contract.functions.getClimbingLocationCount().call() - 1
            await message.reply_text(
                f"Climb created, {user.first_name}! 🪨 {build_data['name']} ({build_data['difficulty']}) "
                f"at ({latitude/10**6:.4f}, {longitude/10**6:.4f}). Tx: {tx_hash.hex()}"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=(
                    f"New climb by {user.username}! 🧗\n"
                    f"Name: {build_data['name']} ({build_data['difficulty']})\n"
                    f"Location: ({latitude/10**6:.4f}, {longitude/10**6:.4f})\n"
                    f"Tx: {tx_hash.hex()}"
                )
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")

        context.user_data.pop('buildaclimb', None)
    except Exception as e:
        logger.error(f"Error in handle_location: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def find_a_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /findaclimb in the chat! 🧗"
            )
        return

    try:
        location_count = contract.functions.getClimbingLocationCount().call()
        if location_count == 0:
            await message.reply_text(
                "No climbs yet! Create one with /buildaclimb 🪨"
            )
            return

        tour_list = []
        for i in range(location_count):
            location = contract.functions.climbingLocations(i).call()
            tour_list.append(
                f"🏔️ {location[1]} ({location[2]}) - By {location[0][:6]}...\n"
                f"   Location: ({location[3]/10**6:.4f}, {location[4]/10**6:.4f})\n"
                f"   Map: https://www.google.com/maps?q={location[3]/10**6},{location[4]/10**6}"
            )
        await message.reply_text(
            f"Discover Climbs:\n" + "\n".join(tour_list) + "\n"
            "Create your own with /buildaclimb or buy one with /purchaseclimb! 🌄"
        )
    except Exception as e:
        logger.error(f"Error in /findaclimb: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def purchase_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /purchaseclimb in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Provide a location ID, e.g., /purchaseclimb 1 🪙")
            return
        location_id = int(context.args[0])
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        location_cost = contract.functions.locationCreationCost().call()
        gas_estimate = contract.functions.purchaseClimbingLocation(location_id).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)

        # Approve $TOURS spending
        approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, location_cost).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_approve = w3.eth.account.sign_transaction(approve_tx, PRIVATE_KEY)
        approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
        w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)

        # Purchase climb
        tx = contract.functions.purchaseClimbingLocation(location_id).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce + 1,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Climb #{location_id} purchased, {user.first_name}! 🎉 Tx: {tx_hash.hex()}"
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /purchaseclimb: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def create_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /createtournament in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Set an entry fee in $TOURS, e.g., /createtournament 10 🏆")
            return
        entry_fee = int(float(context.args[0]) * 10**18)
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        gas_estimate = contract.functions.createTournament(entry_fee).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.createTournament(entry_fee).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            tournament_id = contract.functions.getTournamentCount().call() - 1
            await message.reply_text(
                f"Tournament #{tournament_id} created with {entry_fee/10**18} $TOURS fee, {user.first_name}! 🏆 "
                f"Tx: {tx_hash.hex()}"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=(
                    f"New tournament #{tournament_id} by {user.username}! 🏆\n"
                    f"Entry Fee: {entry_fee/10**18} $TOURS\n"
                    f"Join with /jointournament {tournament_id}\n"
                    f"Tx: {tx_hash.hex()}"
                )
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /createtournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def join_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /jointournament in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Provide a tournament ID, e.g., /jointournament 1 🏆")
            return
        tournament_id = int(context.args[0])
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        tournament = contract.functions.tournaments(tournament_id).call()
        entry_fee = tournament[0]
        gas_estimate = contract.functions.joinTournament(tournament_id).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)

        # Approve $TOURS spending
        approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, entry_fee).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_approve = w3.eth.account.sign_transaction(approve_tx, PRIVATE_KEY)
        approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
        w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)

        # Join tournament
        tx = contract.functions.joinTournament(tournament_id).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce + 1,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Joined tournament #{tournament_id}, {user.first_name}! 🏆 Tx: {tx_hash.hex()}"
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /jointournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def end_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /endtournament in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if len(context.args) < 2:
            await message.reply_text("Provide tournament ID and winner, e.g., /endtournament 1 0xWinner 🏆")
            return
        tournament_id = int(context.args[0])
        winner_address = context.args[1]
        if not w3.is_address(winner_address):
            await message.reply_text("Invalid winner address! 😕")
            return

        if account.address.lower() != OWNER_ADDRESS.lower():
            await message.reply_text("Only the owner can end tournaments! 🚫")
            return

        gas_estimate = contract.functions.endTournament(tournament_id, winner_address).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.endTournament(tournament_id, winner_address).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Tournament #{tournament_id} ended with winner {winner_address}! 🏆 Tx: {tx_hash.hex()}"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=(
                    f"Tournament #{tournament_id} ended! 🏆\n"
                    f"Winner: {winner_address}\n"
                    f"Tx: {tx_hash.hex()}"
                )
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /endtournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def balance(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /balance in the chat! 🧗"
            )
        return

    try:
        balance_wei = w3.eth.get_balance(account.address)
        balance_mon = w3.from_wei(balance_wei, 'ether')
        tours_balance = tours_contract.functions.balanceOf(account.address).call() / 10**18
        await message.reply_text(
            f"💰 Wallet Balance:\n"
            f"- {balance_mon:.4f} $MON\n"
            f"- {tours_balance:.2f} $TOURS\n"
            f"Address: {account.address}\n"
            "Top up $MON at https://testnet.monad.xyz/faucet! 🪙"
        )
    except Exception as e:
        logger.error(f"Error in /balance: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def help_command(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /help in the chat! 🧗"
            )
        return

    help_text = (
        "🏔️ EmpowerTours Commands 🧗‍♀️\n\n"
        "/start - Kick off your adventure\n"
        "/tutorial - Learn to set up your wallet and profile\n"
        "/createprofile <wallet> - Join with 1 $MON\n"
        "/journal <description> - Log climbs, earn $TOURS\n"
        "/comment <entry_id> <text> - Comment on journals (0.1 $MON)\n"
        "/buildaclimb <name> <difficulty> - Share a climb (10 $TOURS)\n"
        "/purchaseclimb <location_id> - Buy a climb (10 $TOURS)\n"
        "/findaclimb - Explore climbing spots\n"
        "/createtournament <entry_fee> - Start a tournament\n"
        "/jointournament <tournament_id> - Join a tournament\n"
        "/endtournament <tournament_id> <winner> - End a tournament (owner only)\n"
        "/balance - Check your $MON and $TOURS\n"
        "/help - See this menu\n\n"
        "Join the fun at https://t.me/empowertourschat! 🌄"
    )
    await message.reply_text(help_text)

async def monitor_events(context):
    try:
        latest_block = w3.eth.get_block('latest').number
        events = contract.events.ClimbingLocationCreated.get_logs(fromBlock=latest_block-10, toBlock=latest_block)
        for event in events:
            location_id = event['args']['locationId']
            creator = event['args']['creator']
            name = event['args']['name']
            tx_hash = event['transactionHash'].hex()
            location = contract.functions.climbingLocations(location_id).call()
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=(
                    f"New climb by {creator[:6]}...! 🧗\n"
                    f"Name: {name}\n"
                    f"Location: ({location[3]/10**6:.4f}, {location[4]/10**6:.4f})\n"
                    f"Tx: {tx_hash}"
                )
            )
    except Exception as e:
        logger.error(f"Error in monitor_events: {str(e)}")

async def main():
    try:
        logger.info("Starting bot...")
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("tutorial", tutorial))
        app.add_handler(CommandHandler("createprofile", create_profile))
        app.add_handler(CommandHandler("journal", journal_entry))
        app.add_handler(CommandHandler("comment", add_comment))
        app.add_handler(CommandHandler("buildaclimb", build_a_climb))
        app.add_handler(CommandHandler("purchaseclimb", purchase_climb))
        app.add_handler(CommandHandler("findaclimb", find_a_climb))
        app.add_handler(CommandHandler("createtournament", create_tournament))
        app.add_handler(CommandHandler("jointournament", join_tournament))
        app.add_handler(CommandHandler("endtournament", end_tournament))
        app.add_handler(CommandHandler("balance", balance))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        app.job_queue.run_repeating(monitor_events, interval=30)
        logger.info("Initializing application...")
        await app.initialize()
        logger.info("Checking bot membership in @empowertourschat...")
        try:
            chat = await app.bot.get_chat(CHAT_HANDLE)
            logger.info(f"Bot is a member of {CHAT_HANDLE} (ID: {chat.id})")
        except Exception as e:
            logger.error(f"Bot not in {CHAT_HANDLE}: {str(e)}")
            raise Exception(f"Ensure bot is a member of {CHAT_HANDLE}")
        logger.info("Starting polling...")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
from telegram import Update
from web3 import Web3
from dotenv import load_dotenv
from eth_account import Account

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
TOURS_TOKEN_ADDRESS = os.getenv("TOURS_TOKEN_ADDRESS")
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS")
LEGACY_ADDRESS = os.getenv("LEGACY_ADDRESS")
CHAT_HANDLE = "@empowertourschat"  # Telegram group handle

# Connect to Monad testnet
w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL))
account = Account.from_key(PRIVATE_KEY)

# EmpowerTours contract ABI
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
            {"indexed": True, "internalType": "address", "name": "previousOwner", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "newOwner", "type": "address"}
        ],
        "name": "OwnershipTransferred",
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
            {"internalType": "string", "name": "contentHash", "type": "string"}
        ],
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
        "inputs": [],
        "name": "getClimbingLocationCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "entryId", "type": "uint256"}
        ],
        "name": "getCommentCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getJournalEntryCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getTournamentCount",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
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
        "inputs": [
            {"internalType": "uint256", "name": "locationId", "type": "uint256"}
        ],
        "name": "purchaseClimbingLocation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
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
        "name": "commentFee",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "journalComments",
        "outputs": [
            {"internalType": "address", "name": "commenter", "type": "address"},
            {"internalType": "string", "name": "contentHash", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "journalEntries",
        "outputs": [
            {"internalType": "address", "name": "author", "type": "address"},
            {"internalType": "string", "name": "contentHash", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "journalReward",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "legacyWallet",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "locationCreationCost",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
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
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "renounceOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "tournaments",
        "outputs": [
            {"internalType": "uint256", "name": "entryFee", "type": "uint256"},
            {"internalType": "uint256", "name": "totalPot", "type": "uint256"},
            {"internalType": "address", "name": "winner", "type": "address"},
            {"internalType": "bool", "name": "isActive", "type": "bool"},
            {"internalType": "uint256", "name": "startTime", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "toursToken",
        "outputs": [
            {"internalType": "contract IERC20", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "newOwner", "type": "address"}
        ],
        "name": "transferOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# ToursToken ABI
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
    }
]

# Initialize contracts
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
tours_contract = w3.eth.contract(address=TOURS_TOKEN_ADDRESS, abi=TOURS_ABI)

# Ensure Web3 connection
if not w3.is_connected():
    logger.error("Failed to connect to Monad testnet")
    raise ConnectionError("Cannot connect to Monad testnet")

# Helper function to get message or edited_message
def get_message(update):
    if update.message:
        return update.message, "message"
    elif update.edited_message:
        return update.edited_message, "edited_message"
    return None, None

# Helper function to get dynamic gas fees
def get_gas_fees():
    try:
        base_fee = w3.eth.get_block('latest')['baseFeePerGas']
        max_priority_fee = w3.eth.max_priority_fee
        max_fee_per_gas = base_fee + max_priority_fee
        return {
            'maxFeePerGas': max_fee_per_gas,
            'maxPriorityFeePerGas': max_priority_fee
        }
    except Exception as e:
        logger.error(f"Error fetching gas fees: {str(e)}")
        return {
            'maxFeePerGas': w3.to_wei('2', 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei('1', 'gwei')
        }

async def start(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /start in the chat to begin! 🧗"
            )
        return
    await message.reply_text(
        "Welcome to EmpowerTours, your rock climbing adventure hub! 🌄\n"
        "New here? Start with /tutorial to set up your Monad wallet and profile.\n"
        "Ready to climb? Join our community at https://t.me/empowertourschat! 🪨"
    )

async def tutorial(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /tutorial in the chat to learn how to start! 🧗"
            )
        return

    tutorial_text = (
        "🌟 Welcome to EmpowerTours Tutorial! 🌟\n\n"
        "Let's get you climbing on the Monad blockchain! Follow these steps:\n\n"
        "1️⃣ **Create a Monad Wallet**:\n"
        "   - Download a wallet like MetaMask[](https://metamask.io).\n"
        "   - Set up a new wallet and securely save your seed phrase.\n"
        "   - Add the Monad testnet to MetaMask:\n"
        "     - Network Name: Monad Testnet\n"
        "     - RPC URL: https://testnet-rpc.monad.xyz\n"
        "     - Chain ID: 10143\n"
        "     - Currency: MON\n"
        "   - Get testnet $MON from the faucet: https://testnet.monad.xyz/faucet\n\n"
        "2️⃣ **Create Your Profile**:\n"
        "   - Use /createprofile <your_wallet_address> (e.g., /createprofile 0x123...).\n"
        "   - Send 1 $MON to join the EmpowerTours community!\n\n"
        "3️⃣ **Explore the App**:\n"
        "   - /journal <description>: Log your climbs and earn $TOURS (send a photo after).\n"
        "   - /buildaclimb <name> <difficulty>: Create a climbing location (10 $TOURS).\n"
        "   - /purchaseclimb <location_id>: Buy access to climbs.\n"
        "   - /createtournament <entry_fee>: Start a tournament to win big!\n"
        "   - /findaclimb: Discover climbing spots worldwide.\n"
        "   - /help: See all commands.\n\n"
        "4️⃣ **Join the Community**:\n"
        "   - Chat with climbers at https://t.me/empowertourschat.\n"
        "   - Share your adventures and compete in tournaments!\n\n"
        "Need help? Just ask! Ready to start? Try /createprofile now! 🪨✨"
    )
    await message.reply_text(tutorial_text)

async def create_profile(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /createprofile in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text(
                "Please provide your wallet address, e.g., /createprofile 0xYourAddress 🪙"
            )
            return
        wallet_address = context.args[0]
        if not w3.is_address(wallet_address):
            await message.reply_text("Invalid wallet address! Use a valid Monad address. 😕")
            return

        profile_fee = contract.functions.profileFee().call()
        balance = w3.eth.get_balance(account.address)
        gas_estimate = contract.functions.createProfile().estimate_gas({
            'from': account.address,
            'value': profile_fee
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        gas_cost = gas_limit * gas_fees['maxFeePerGas']

        if balance < gas_cost + profile_fee:
            await message.reply_text(
                f"Oops! Need {w3.from_wei(profile_fee + gas_cost, 'ether')} $MON for profile creation. "
                f"Your balance: {w3.from_wei(balance, 'ether')} $MON. "
                "Top up at https://testnet.monad.xyz/faucet! 🪙"
            )
            return

        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.createProfile().build_transaction({
            'chainId': 10143,
            'from': account.address,
            'value': profile_fee,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            context.user_data['wallet_address'] = wallet_address
            await message.reply_text(
                f"Welcome aboard, {user.first_name}! Your profile is live! 🎉 Tx: {tx_hash.hex()}\n"
                "Try /journal to log your first climb or /buildaclimb to share a spot! 🪨"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=f"New climber {user.username} joined EmpowerTours! 🧗 Tx: {tx_hash.hex()}"
            )
        else:
            await message.reply_text("Transaction failed. Try again, you got this! 💪")
    except Exception as e:
        logger.error(f"Error in /createprofile: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def journal_entry(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /journal in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text(
                "Share your climb story, e.g., /journal Conquered Mt. Monad! Then send a photo. 📸"
            )
            return
        content = " ".join(context.args)
        content_hash = w3.keccak(text=content).hex()

        context.user_data['journal'] = {
            'user_id': user.id,
            'username': user.username,
            'content_hash': content_hash,
            'awaiting_photo': True
        }
        await message.reply_text(
            f"Awesome story, {user.first_name}! Send a photo to complete your journal entry. 🌟"
        )
    except Exception as e:
        logger.error(f"Error in /journal: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def handle_journal_photo(update: Update, context):
    message, update_type = get_message(update)
    if message is None or not message.photo:
        return

    try:
        user = message.from_user
        journal_data = context.user_data.get('journal')
        if not journal_data or not journal_data.get('awaiting_photo'):
            return

        photo_id = message.photo[-1].file_id
        journal_data['photo_id'] = photo_id
        journal_data['awaiting_photo'] = False

        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        gas_estimate = contract.functions.addJournalEntry(journal_data['content_hash']).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.addJournalEntry(journal_data['content_hash']).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Journal entry logged, {user.first_name}! You earned 5 $TOURS! 🎉 Tx: {tx_hash.hex()}"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=f"{user.username} shared a climb journal! 🪨 Check it out! Tx: {tx_hash.hex()}"
            )
            context.user_data.pop('journal', None)
        else:
            await message.reply_text("Transaction failed. Try again, climber! 💪")
    except Exception as e:
        logger.error(f"Error in handle_journal_photo: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def add_comment(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /comment in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if len(context.args) < 2:
            await message.reply_text(
                "Add a comment, e.g., /comment 1 Epic climb! (Costs 0.1 $MON) 🗣️"
            )
            return
        entry_id = int(context.args[0])
        comment = " ".join(context.args[1:])
        comment_hash = w3.keccak(text=comment).hex()
        comment_fee = contract.functions.commentFee().call()

        balance = w3.eth.get_balance(account.address)
        gas_estimate = contract.functions.addComment(entry_id, comment_hash).estimate_gas({
            'from': account.address,
            'value': comment_fee
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        gas_cost = gas_limit * gas_fees['maxFeePerGas']

        if balance < gas_cost + comment_fee:
            await message.reply_text(
                f"Need {w3.from_wei(comment_fee + gas_cost, 'ether')} $MON to comment. "
                "Top up at https://testnet.monad.xyz/faucet! 🪙"
            )
            return

        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.addComment(entry_id, comment_hash).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'value': comment_fee,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Comment added to entry #{entry_id}, {user.first_name}! 🎉 Tx: {tx_hash.hex()}"
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /comment: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def build_a_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /buildaclimb in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if len(context.args) < 2:
            await message.reply_text(
                "Share a climb spot, e.g., /buildaclimb EpicPeak Hard. Then send a photo and location. 📍"
            )
            return
        name = context.args[0]
        difficulty = context.args[1].capitalize()

        context.user_data['buildaclimb'] = {
            'name': name,
            'difficulty': difficulty,
            'user_id': user.id,
            'username': user.username,
            'awaiting_photo': True
        }
        await message.reply_text(
            f"Nice one, {user.first_name}! Send a photo of the climbing spot. 📸"
        )
    except Exception as e:
        logger.error(f"Error in /buildaclimb: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def handle_photo(update: Update, context):
    message, update_type = get_message(update)
    if message is None or not message.photo:
        return

    try:
        user = message.from_user
        build_data = context.user_data.get('buildaclimb')
        journal_data = context.user_data.get('journal')
        if build_data and build_data.get('awaiting_photo'):
            photo_id = message.photo[-1].file_id
            build_data['photo_id'] = photo_id
            build_data['awaiting_photo'] = False
            build_data['awaiting_location'] = True
            await message.reply_text(
                f"Photo received, {user.first_name}! Now share the location of the climb. 📍"
            )
        elif journal_data and journal_data.get('awaiting_photo'):
            await handle_journal_photo(update, context)
    except Exception as e:
        logger.error(f"Error in handle_photo: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def handle_location(update: Update, context):
    message, update_type = get_message(update)
    if message is None or not message.location:
        return

    try:
        user = message.from_user
        build_data = context.user_data.get('buildaclimb')
        if not build_data or not build_data.get('awaiting_location'):
            return

        latitude = int(message.location.latitude * 10**6)
        longitude = int(message.location.longitude * 10**6)
        photo_hash = build_data['photo_id']

        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        gas_estimate = contract.functions.createClimbingLocation(
            build_data['name'], build_data['difficulty'], latitude, longitude, photo_hash
        ).estimate_gas({'from': account.address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)

        # Approve $TOURS spending
        location_cost = contract.functions.locationCreationCost().call()
        approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, location_cost).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': g_fees['maxPriorityFeePerGas']
        })
        signed_approve = w3.eth.account.sign_transaction(approve_tx, PRIVATE_KEY)
        approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
        w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)

        # Create climbing location
        tx = contract.functions.createClimbingLocation(
            build_data['name'], build_data['difficulty'], latitude, longitude, photo_hash
        ).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce + 1,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            location_id = contract.functions.getClimbingLocationCount().call() - 1
            await message.reply_text(
                f"Climb created, {user.first_name}! 🪨 {build_data['name']} ({build_data['difficulty']}) "
                f"at ({latitude/10**6:.4f}, {longitude/10**6:.4f}). Tx: {tx_hash.hex()}"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=(
                    f"New climb by {user.username}! 🧗\n"
                    f"Name: {build_data['name']} ({build_data['difficulty']})\n"
                    f"Location: ({latitude/10**6:.4f}, {longitude/10**6:.4f})\n"
                    f"Tx: {tx_hash.hex()}"
                )
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")

        context.user_data.pop('buildaclimb', None)
    except Exception as e:
        logger.error(f"Error in handle_location: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def find_a_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /findaclimb in the chat! 🧗"
            )
        return

    try:
        location_count = contract.functions.getClimbingLocationCount().call()
        if location_count == 0:
            await message.reply_text(
                "No climbs yet! Create one with /buildaclimb 🪨"
            )
            return

        tour_list = []
        for i in range(location_count):
            location = contract.functions.climbingLocations(i).call()
            tour_list.append(
                f"🏔️ {location[1]} ({location[2]}) - By {location[0][:6]}...\n"
                f"   Location: ({location[3]/10**6:.4f}, {location[4]/10**6:.4f})\n"
                f"   Map: https://www.google.com/maps?q={location[3]/10**6},{location[4]/10**6}"
            )
        await message.reply_text(
            f"Discover Climbs:\n" + "\n".join(tour_list) + "\n"
            "Create your own with /buildaclimb or buy one with /purchaseclimb! 🌄"
        )
    except Exception as e:
        logger.error(f"Error in /findaclimb: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def purchase_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /purchaseclimb in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Provide a location ID, e.g., /purchaseclimb 1 🪙")
            return
        location_id = int(context.args[0])
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        location_cost = contract.functions.locationCreationCost().call()
        gas_estimate = contract.functions.purchaseClimbingLocation(location_id).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)

        # Approve $TOURS spending
        approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, location_cost).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_approve = w3.eth.account.sign_transaction(approve_tx, PRIVATE_KEY)
        approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
        w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)

        # Purchase climb
        tx = contract.functions.purchaseClimbingLocation(location_id).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce + 1,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Climb #{location_id} purchased, {user.first_name}! 🎉 Tx: {tx_hash.hex()}"
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /purchaseclimb: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def create_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /createtournament in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Set an entry fee in $TOURS, e.g., /createtournament 10 🏆")
            return
        entry_fee = int(float(context.args[0]) * 10**18)
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        gas_estimate = contract.functions.createTournament(entry_fee).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.createTournament(entry_fee).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            tournament_id = contract.functions.getTournamentCount().call() - 1
            await message.reply_text(
                f"Tournament #{tournament_id} created with {entry_fee/10**18} $TOURS fee, {user.first_name}! 🏆 "
                f"Tx: {tx_hash.hex()}"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=(
                    f"New tournament #{tournament_id} by {user.username}! 🏆\n"
                    f"Entry Fee: {entry_fee/10**18} $TOURS\n"
                    f"Join with /jointournament {tournament_id}\n"
                    f"Tx: {tx_hash.hex()}"
                )
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /createtournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def join_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /jointournament in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Provide a tournament ID, e.g., /jointournament 1 🏆")
            return
        tournament_id = int(context.args[0])
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Set your wallet with /createprofile first! 🪙")
            return

        tournament = contract.functions.tournaments(tournament_id).call()
        entry_fee = tournament[0]
        gas_estimate = contract.functions.joinTournament(tournament_id).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)

        # Approve $TOURS spending
        approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, entry_fee).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': 100000,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_approve = w3.eth.account.sign_transaction(approve_tx, PRIVATE_KEY)
        approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
        w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)

        # Join tournament
        tx = contract.functions.joinTournament(tournament_id).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce + 1,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Joined tournament #{tournament_id}, {user.first_name}! 🏆 Tx: {tx_hash.hex()}"
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /jointournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def end_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /endtournament in the chat! 🧗"
            )
        return

    try:
        user = message.from_user
        if len(context.args) < 2:
            await message.reply_text("Provide tournament ID and winner, e.g., /endtournament 1 0xWinner 🏆")
            return
        tournament_id = int(context.args[0])
        winner_address = context.args[1]
        if not w3.is_address(winner_address):
            await message.reply_text("Invalid winner address! 😕")
            return

        if account.address.lower() != OWNER_ADDRESS.lower():
            await message.reply_text("Only the owner can end tournaments! 🚫")
            return

        gas_estimate = contract.functions.endTournament(tournament_id, winner_address).estimate_gas({
            'from': account.address
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = get_gas_fees()
        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.endTournament(tournament_id, winner_address).build_transaction({
            'chainId': 10143,
            'from': account.address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })

        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        if receipt.status == 1:
            await message.reply_text(
                f"Tournament #{tournament_id} ended with winner {winner_address}! 🏆 Tx: {tx_hash.hex()}"
            )
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=(
                    f"Tournament #{tournament_id} ended! 🏆\n"
                    f"Winner: {winner_address}\n"
                    f"Tx: {tx_hash.hex()}"
                )
            )
        else:
            await message.reply_text("Transaction failed. Try again! 💪")
    except Exception as e:
        logger.error(f"Error in /endtournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def balance(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /balance in the chat! 🧗"
            )
        return

    try:
        balance_wei = w3.eth.get_balance(account.address)
        balance_mon = w3.from_wei(balance_wei, 'ether')
        tours_balance = tours_contract.functions.balanceOf(account.address).call() / 10**18
        await message.reply_text(
            f"💰 Wallet Balance:\n"
            f"- {balance_mon:.4f} $MON\n"
            f"- {tours_balance:.2f} $TOURS\n"
            f"Address: {account.address}\n"
            "Top up $MON at https://testnet.monad.xyz/faucet! 🪙"
        )
    except Exception as e:
        logger.error(f"Error in /balance: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def help_command(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "Use /help in the chat! 🧗"
            )
        return

    help_text = (
        "🏔️ EmpowerTours Commands 🧗‍♀️\n\n"
        "/start - Kick off your adventure\n"
        "/tutorial - Learn to set up your wallet and profile\n"
        "/createprofile <wallet> - Join with 1 $MON\n"
        "/journal <description> - Log climbs, earn $TOURS\n"
        "/comment <entry_id> <text> - Comment on journals (0.1 $MON)\n"
        "/buildaclimb <name> <difficulty> - Share a climb (10 $TOURS)\n"
        "/purchaseclimb <location_id> - Buy a climb (10 $TOURS)\n"
        "/findaclimb - Explore climbing spots\n"
        "/createtournament <entry_fee> - Start a tournament\n"
        "/jointournament <tournament_id> - Join a tournament\n"
        "/endtournament <tournament_id> <winner> - End a tournament (owner only)\n"
        "/balance - Check your $MON and $TOURS\n"
        "/help - See this menu\n\n"
        "Join the fun at https://t.me/empowertourschat! 🌄"
    )
    await message.reply_text(help_text)

async def monitor_events(context):
    try:
        latest_block = w3.eth.get_block('latest').number
        events = contract.events.ClimbingLocationCreated.get_logs(fromBlock=latest_block-10, toBlock=latest_block)
        for event in events:
            location_id = event['args']['locationId']
            creator = event['args']['creator']
            name = event['args']['name']
            tx_hash = event['transactionHash'].hex()
            location = contract.functions.climbingLocations(location_id).call()
            await context.bot.send_message(
                chat_id=CHAT_HANDLE,
                text=(
                    f"New climb by {creator[:6]}...! 🧗\n"
                    f"Name: {name}\n"
                    f"Location: ({location[3]/10**6:.4f}, {location[4]/10**6:.4f})\n"
                    f"Tx: {tx_hash}"
                )
            )
    except Exception as e:
        logger.error(f"Error in monitor_events: {str(e)}")

async def main():
    try:
        logger.info("Starting bot...")
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("tutorial", tutorial))
        app.add_handler(CommandHandler("createprofile", create_profile))
        app.add_handler(CommandHandler("journal", journal_entry))
        app.add_handler(CommandHandler("comment", add_comment))
        app.add_handler(CommandHandler("buildaclimb", build_a_climb))
        app.add_handler(CommandHandler("purchaseclimb", purchase_climb))
        app.add_handler(CommandHandler("findaclimb", find_a_climb))
        app.add_handler(CommandHandler("createtournament", create_tournament))
        app.add_handler(CommandHandler("jointournament", join_tournament))
        app.add_handler(CommandHandler("endtournament", end_tournament))
        app.add_handler(CommandHandler("balance", balance))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        app.job_queue.run_repeating(monitor_events, interval=30)
        logger.info("Initializing application...")
        await app.initialize()
        logger.info("Checking bot membership in @empowertourschat...")
        try:
            chat = await app.bot.get_chat(CHAT_HANDLE)
            logger.info(f"Bot is a member of {CHAT_HANDLE} (ID: {chat.id})")
        except Exception as e:
            logger.error(f"Bot not in {CHAT_HANDLE}: {str(e)}")
            raise Exception(f"Ensure bot is a member of {CHAT_HANDLE}")
        logger.info("Starting polling...")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
