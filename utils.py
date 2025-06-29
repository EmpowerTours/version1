from web3 import Web3
from dotenv import load_dotenv
import os

load_dotenv()
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL")
w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL))

def get_message(update):
    if update.message:
        return update.message, "message"
    elif update.edited_message:
        return update.edited_message, "edited_message"
    return None, None
