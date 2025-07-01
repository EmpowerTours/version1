from web3 import Web3
from dotenv import load_dotenv
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL", "https://testnet-rpc.monad.xyz")

# Initialize Web3 connection
try:
    w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL))
    if not w3.is_connected():
        logger.error("Failed to connect to Monad testnet. Check MONAD_RPC_URL.")
        w3 = None
except Exception as e:
    logger.error(f"Error initializing Web3: {str(e)}")
    w3 = None

def get_message(update):
    if update.message:
        return update.message, "message"
    elif update.edited_message:
        return update.edited_message, "edited_message"
    return None, None
