import os
import asyncio
import logging
import json
import requests
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from dotenv import load_dotenv
from contract import (
    create_profile_tx, add_journal_entry_tx, add_comment_tx, create_climbing_location_tx,
    purchase_climbing_location_tx, create_tournament_tx, join_tournament_tx, end_tournament_tx,
    get_climbing_locations
)
from utils import get_message

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "https://your-bot-api.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://empowertours-connect.vercel.app")
CHAT_HANDLE = "@empowertourschat"

async def start(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /start in the chat to begin! 🧗")
        return
    await message.reply_text(
        """Welcome to EmpowerTours, your rock climbing adventure hub! 🌄
New here? Start with /tutorial to set up your wallet and profile.
Ready to climb? Join our community at <a href="https://t.me/empowertourschat">EmpowerTours Chat</a>! 🪨""",
        parse_mode="HTML"
    )

async def tutorial(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /tutorial in the chat to learn how to start! 🧗")
        return

    tutorial_text = """🌟 Welcome to EmpowerTours Tutorial! 🌟

Let's get you climbing on the Monad blockchain! Follow these steps:

1️⃣ **Create a Monad Wallet**:
   - Download a wallet like <a href="https://metamask.io">MetaMask</a>, <a href="https://phantom.app">Phantom</a>, or set up a multi-signature wallet with <a href="https://gnosis-safe.io">Gnosis Safe</a>.
   - Set up your wallet and securely save your seed phrase or private keys.
   - For multi-sig wallets, configure multiple signers for security.
   - Add the Monad testnet to your wallet:
     - Network Name: Monad Testnet
     - RPC URL: https://testnet-rpc.monad.xyz
     - Chain ID: 10143
     - Currency: MON
   - Get testnet $MON from the faucet: <a href="https://testnet.monad.xyz/faucet">Monad Faucet</a>

2️⃣ **Connect Your Wallet**:
   - Use /connectwallet to get a link to connect your wallet (MetaMask, Phantom, or multi-sig) via WalletConnect.
   - Follow the link to connect and sign transactions directly in your wallet.

3️⃣ **Create Your Profile**:
   - Use /createprofile to create your profile (1 $MON fee, signed in your wallet).

4️⃣ **Explore the App**:
   - /journal <description>: Log your climbs and earn $TOURS (send a photo after).
   - /buildaclimb <name> <difficulty>: Create a climbing location (10 $TOURS).
   - /purchaseclimb <location_id>: Buy access to climbs.
   - /createtournament <entry_fee>: Start a tournament to win big!
   - /findaclimb: Discover climbing spots worldwide.
   - /help: See all commands.

5️⃣ **Join the Community**:
   - Chat with climbers at <a href="https://t.me/empowertourschat">EmpowerTours Chat</a>.
   - Share your adventures and compete in tournaments!

Need help? Just ask! Ready to start? Try /connectwallet now! 🪨✨"""
    await message.reply_text(tutorial_text, parse_mode="HTML")

async def connect_wallet(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /connectwallet in the chat! 🧗")
        return

    try:
        user = message.from_user
        response = requests.post(f"{API_BASE_URL}/connect", json={'user_id': str(user.id)})
        if response.status_code != 200:
            await message.reply_text("Failed to initiate wallet connection. Try again! 😅")
            return
        response_data = response.json()
        connect_url = f"{FRONTEND_URL}?userId={user.id}&sessionId={response_data['session_id']}"
        await message.reply_text(
            f"Please connect your wallet (MetaMask, Phantom, etc.) by visiting this link:\n"
            f"<a href=\"{connect_url}\">Connect Wallet</a>\n"
            f"Follow the instructions to connect and sign transactions directly in your wallet.",
            parse_mode="HTML"
        )
        context.user_data['wc_session'] = {'user_id': user.id, 'session_id': response_data['session_id']}
    except Exception as e:
        logger.error(f"Error in /connectwallet: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def create_profile(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /createprofile in the chat! 🧗")
        return

    try:
        user = message.from_user
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        result = await create_profile_tx(wallet_address, user)
        if result['status'] == 'success':
            response = requests.post(f"{API_BASE_URL}/sign", json={
                'user_id': str(user.id),
                'tx_data': result['tx_data']
            })
            if response.status_code == 200:
                await message.reply_text(
                    f"Please visit the WalletConnect page to sign the profile creation transaction (1 $MON fee).\n"
                    f"If not redirected, use /connectwallet to get the link again."
                )
            else:
                await message.reply_text("Failed to initiate transaction signing. Try again! 😅")
        else:
            await message.reply_text(result['message'])
    except Exception as e:
        logger.error(f"Error in /createprofile: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def journal_entry(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /journal in the chat! 🧗")
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text(
                "Share your climb story, e.g., /journal Conquered Mt. Monad! Then send a photo. 📸"
            )
            return
        content = " ".join(context.args)
        context.user_data['journal'] = {
            'user_id': user.id,
            'username': user.username,
            'content': content,
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
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        content_hash = w3.keccak(text=journal_data['content']).hex()
        result = await add_journal_entry_tx(wallet_address, content_hash, user)
        if result['status'] == 'success':
            response = requests.post(f"{API_BASE_URL}/sign", json={
                'user_id': str(user.id),
                'tx_data': result['tx_data']
            })
            if response.status_code == 200:
                await message.reply_text(
                    f"Please visit the WalletConnect page to sign the journal entry transaction (earns 5 $TOURS).\n"
                    f"If not redirected, use /connectwallet to get the link again."
                )
            else:
                await message.reply_text("Failed to initiate transaction signing. Try again! 😅")
            context.user_data.pop('journal', None)
        else:
            await message.reply_text(result['message'])
    except Exception as e:
        logger.error(f"Error in handle_journal_photo: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def add_comment(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /comment in the chat! 🧗")
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
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        result = await add_comment_tx(wallet_address, entry_id, comment, user)
        if result['status'] == 'success':
            response = requests.post(f"{API_BASE_URL}/sign", json={
                'user_id': str(user.id),
                'tx_data': result['tx_data']
            })
            if response.status_code == 200:
                await message.reply_text(
                    f"Please visit the WalletConnect page to sign the comment transaction (0.1 $MON).\n"
                    f"If not redirected, use /connectwallet to get the link again."
                )
            else:
                await message.reply_text("Failed to initiate transaction signing. Try again! 😅")
        else:
            await message.reply_text(result['message'])
    except Exception as e:
        logger.error(f"Error in /comment: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def build_a_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /buildaclimb in the chat! 🧗")
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
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        result = await create_climbing_location_tx(wallet_address, build_data['name'], build_data['difficulty'], latitude, longitude, photo_hash, user)
        if result['status'] == 'success':
            response = requests.post(f"{API_BASE_URL}/sign", json={
                'user_id': str(user.id),
                'tx_data': result['tx_data']
            })
            if response.status_code == 200:
                await message.reply_text(
                    f"Please visit the WalletConnect page to sign the {result['tx_type'].replace('_', ' ')} transaction (10 $TOURS).\n"
                    f"If not redirected, use /connectwallet to get the link again."
                )
            else:
                await message.reply_text("Failed to initiate transaction signing. Try again! 😅")
            context.user_data.pop('buildaclimb', None)
        else:
            await message.reply_text(result['message'])
    except Exception as e:
        logger.error(f"Error in handle_location: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def purchase_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /purchaseclimb in the chat! 🧗")
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Provide a location ID, e.g., /purchaseclimb 1 🪙")
            return
        location_id = int(context.args[0])
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        result = await purchase_climbing_location_tx(wallet_address, location_id, user)
        if result['status'] == 'success':
            response = requests.post(f"{API_BASE_URL}/sign", json={
                'user_id': str(user.id),
                'tx_data': result['tx_data']
            })
            if response.status_code == 200:
                await message.reply_text(
                    f"Please visit the WalletConnect page to sign the {result['tx_type'].replace('_', ' ')} transaction (10 $TOURS).\n"
                    f"If not redirected, use /connectwallet to get the link again."
                )
            else:
                await message.reply_text("Failed to initiate transaction signing. Try again! 😅")
        else:
            await message.reply_text(result['message'])
    except Exception as e:
        logger.error(f"Error in /purchaseclimb: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def create_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /createtournament in the chat! 🧗")
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Set an entry fee in $TOURS, e.g., /createtournament 10 🏆")
            return
        entry_fee = int(float(context.args[0]) * 10**18)
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        result = await create_tournament_tx(wallet_address, entry_fee, user)
        if result['status'] == 'success':
            response = requests.post(f"{API_BASE_URL}/sign", json={
                'user_id': str(user.id),
                'tx_data': result['tx_data']
            })
            if response.status_code == 200:
                await message.reply_text(
                    f"Please visit the WalletConnect page to sign the tournament creation transaction.\n"
                    f"If not redirected, use /connectwallet to get the link again."
                )
            else:
                await message.reply_text("Failed to initiate transaction signing. Try again! 😅")
        else:
            await message.reply_text(result['message'])
    except Exception as e:
        logger.error(f"Error in /createtournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def join_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /jointournament in the chat! 🧗")
        return

    try:
        user = message.from_user
        if not context.args:
            await message.reply_text("Provide a tournament ID, e.g., /jointournament 1 🏆")
            return
        tournament_id = int(context.args[0])
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        result = await join_tournament_tx(wallet_address, tournament_id, user)
        if result['status'] == 'success':
            response = requests.post(f"{API_BASE_URL}/sign", json={
                'user_id': str(user.id),
                'tx_data': result['tx_data']
            })
            if response.status_code == 200:
                await message.reply_text(
                    f"Please visit the WalletConnect page to sign the {result['tx_type'].replace('_', ' ')} transaction.\n"
                    f"If not redirected, use /connectwallet to get the link again."
                )
            else:
                await message.reply_text("Failed to initiate transaction signing. Try again! 😅")
        else:
            await message.reply_text(result['message'])
    except Exception as e:
        logger.error(f"Error in /jointournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def end_tournament(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /endtournament in the chat! 🧗")
        return

    try:
        user = message.from_user
        if len(context.args) < 2:
            await message.reply_text("Provide tournament ID and winner, e.g., /endtournament 1 0xWinner 🏆")
            return
        tournament_id = int(context.args[0])
        winner_address = context.args[1]
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        result = await end_tournament_tx(wallet_address, tournament_id, winner_address, user)
        if result['status'] == 'success':
            response = requests.post(f"{API_BASE_URL}/sign", json={
                'user_id': str(user.id),
                'tx_data': result['tx_data']
            })
            if response.status_code == 200:
                await message.reply_text(
                    f"Please visit the WalletConnect page to sign the tournament end transaction.\n"
                    f"If not redirected, use /connectwallet to get the link again."
                )
            else:
                await message.reply_text("Failed to initiate transaction signing. Try again! 😅")
        else:
            await message.reply_text(result['message'])
    except Exception as e:
        logger.error(f"Error in /endtournament: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def balance(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /balance in the chat! 🧗")
        return

    try:
        wallet_address = context.user_data.get('wallet_address')
        if not wallet_address:
            await message.reply_text("Connect your wallet with /connectwallet first! 🪙")
            return

        balance_wei = w3.eth.get_balance(wallet_address)
        balance_mon = w3.from_wei(balance_wei, 'ether')
        tours_balance = tours_contract.functions.balanceOf(wallet_address).call() / 10**18
        await message.reply_text(
            f"💰 Wallet Balance:\n"
            f"- {balance_mon:.4f} $MON\n"
            f"- {tours_balance:.2f} $TOURS\n"
            f"Address: {wallet_address}\n"
            "Top up $MON at <a href=\"https://testnet.monad.xyz/faucet\">Monad Faucet</a>! 🪙",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in /balance: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def find_a_climb(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /findaclimb in the chat! 🧗")
        return

    try:
        tour_list = await get_climbing_locations()
        if not tour_list:
            await message.reply_text(
                "No climbs yet! Create one with /buildaclimb 🪨"
            )
            return
        await message.reply_text(
            f"Discover Climbs:\n" + "\n".join(tour_list) + "\n"
            "Create your own with /buildaclimb or buy one with /purchaseclimb! 🌄"
        )
    except Exception as e:
        logger.error(f"Error in /findaclimb: {str(e)}")
        await message.reply_text(f"Oops, something went wrong: {str(e)}. Try again! 😅")

async def help_command(update: Update, context):
    message, update_type = get_message(update)
    if message is None:
        logger.warning(f"Received non-message update: {update.to_dict()}")
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("Use /help in the chat! 🧗")
        return

    help_text = """🏔️ EmpowerTours Commands 🧗‍♀️

/start - Kick off your adventure
/tutorial - Learn to set up your wallet and profile
/connectwallet - Connect your wallet (MetaMask, Phantom, etc.)
/createprofile - Join with 1 $MON
/journal <description> - Log climbs, earn $TOURS
/comment <entry_id> <text> - Comment on journals (0.1 $MON)
/buildaclimb <name> <difficulty> - Share a climb (10 $TOURS)
/purchaseclimb <location_id> - Buy a climb (10 $TOURS)
/findaclimb - Explore climbing spots
/createtournament <entry_fee> - Start a tournament
/jointournament <tournament_id> - Join a tournament
/endtournament <tournament_id> <winner> - End a tournament (owner only)
/balance - Check your $MON and $TOURS
/help - See this menu

Join the fun at <a href="https://t.me/empowertourschat">EmpowerTours Chat</a>! 🌄"""
    await message.reply_text(help_text, parse_mode="HTML")

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
        app.add_handler(CommandHandler("connectwallet", connect_wallet))
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
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise
    finally:
        logger.info("Shutting down application...")
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except Exception as e:
        logger.error(f"Application failed: {str(e)}")
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
