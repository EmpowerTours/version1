import os
import json
import sqlite3
import logging
from web3 import Web3
from web3.exceptions import ContractLogicError
from dotenv import load_dotenv
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL", "https://testnet-rpc.monad.xyz")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
TOURS_TOKEN_ADDRESS = os.getenv("TOURS_TOKEN_ADDRESS")
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS")
LEGACY_ADDRESS = os.getenv("LEGACY_ADDRESS")
API_BASE_URL = os.getenv("API_BASE_URL")
CHAT_HANDLE = os.getenv("CHAT_HANDLE", "@empowertourschat")

# Initialize Web3 with retry logic
w3 = None
contract = None
tours_contract = None

def initialize_web3():
    global w3, contract, tours_contract
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL, request_kwargs={'timeout': 10}))
            if w3.is_connected():
                logger.info("Successfully connected to Monad testnet")
                # EmpowerTours contract ABI
                CONTRACT_ABI = [
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
            {"internalType": "uint256", "name": "entryId", "type": "uint256"},
            {"internalType": "string", "name": "contentHash", "type": "string"},
            {"internalType": "string", "name": "farcasterCastHash", "type": "string"}
        ],
        "name": "addCommentWithFarcaster",
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
            {"internalType": "string", "name": "contentHash", "type": "string"},
            {"internalType": "string", "name": "location", "type": "string"},
            {"internalType": "string", "name": "difficulty", "type": "string"},
            {"internalType": "bool", "name": "isSharedOnFarcaster", "type": "bool"},
            {"internalType": "string", "name": "farcasterCastHash", "type": "string"}
        ],
        "name": "addJournalEntryWithDetails",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "buyTours",
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
        "inputs": [
            {
                "components": [
                    {"internalType": "string", "name": "name", "type": "string"},
                    {"internalType": "string", "name": "difficulty", "type": "string"},
                    {"internalType": "int256", "name": "latitude", "type": "int256"},
                    {"internalType": "int256", "name": "longitude", "type": "int256"},
                    {"internalType": "string", "name": "photoHash", "type": "string"},
                    {"internalType": "bool", "name": "isSharedOnFarcaster", "type": "bool"},
                    {"internalType": "string", "name": "farcasterCastHash", "type": "string"}
                ],
                "internalType": "struct EmpowerTours.ClimbingLocationParams",
                "name": "params",
                "type": "tuple"
            }
        ],
        "name": "createClimbingLocationWithFarcaster",
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
            {"internalType": "uint256", "name": "_farcasterFid", "type": "uint256"},
            {"internalType": "string", "name": "_farcasterUsername", "type": "string"},
            {"internalType": "string", "name": "_farcasterBio", "type": "string"}
        ],
        "name": "createProfileWithFarcaster",
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
            {"internalType": "uint256", "name": "entryFee", "type": "uint256"},
            {"internalType": "string", "name": "tournamentName", "type": "string"},
            {"internalType": "string", "name": "description", "type": "string"},
            {"internalType": "bool", "name": "isSharedOnFarcaster", "type": "bool"},
            {"internalType": "string", "name": "farcasterCastHash", "type": "string"}
        ],
        "name": "createTournamentWithFarcaster",
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
            {"internalType": "uint256", "name": "tournamentId", "type": "uint256"},
            {"internalType": "address", "name": "winner", "type": "address"}
        ],
        "name": "endTournamentWithFarcaster",
        "outputs": [],
        "stateMutability": "nonpayable",
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
            {"internalType": "uint256", "name": "tournamentId", "type": "uint256"}
        ],
        "name": "joinTournamentWithFarcaster",
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
            {"internalType": "uint256", "name": "locationId", "type": "uint256"}
        ],
        "name": "purchaseClimbingLocationWithFarcaster",
        "outputs": [],
        "stateMutability": "nonpayable",
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
            {"internalType": "address", "name": "newOwner", "type": "address"}
        ],
        "name": "transferOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
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
        "name": "FarcasterFidTaken",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "InsufficientFee",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "InsufficientMonSent",
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
        "name": "InvalidFarcasterFid",
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
            {"indexed": True, "internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "creator", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "name", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "difficulty", "type": "string"},
            {"indexed": False, "internalType": "int256", "name": "latitude", "type": "int256"},
            {"indexed": False, "internalType": "int256", "name": "longitude", "type": "int256"},
            {"indexed": False, "internalType": "bool", "name": "isSharedOnFarcaster", "type": "bool"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "ClimbingLocationCreatedEnhanced",
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
            {"indexed": True, "internalType": "address", "name": "commenter", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "contentHash", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "farcasterCastHash", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "CommentAddedEnhanced",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "user", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "castHash", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "contentType", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "contentId", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "FarcasterCastShared",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "user", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "newUsername", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "newBio", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "FarcasterProfileUpdated",
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
            {"indexed": True, "internalType": "address", "name": "author", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "contentHash", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "location", "type": "string"},
            {"indexed": False, "internalType": "string", "name": "difficulty", "type": "string"},
            {"indexed": False, "internalType": "bool", "name": "isSharedOnFarcaster", "type": "bool"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "JournalEntryAddedEnhanced",
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
            {"indexed": True, "internalType": "uint256", "name": "locationId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "buyer", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "LocationPurchasedEnhanced",
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
            {"indexed": True, "internalType": "address", "name": "user", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "farcasterUsername", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "ProfileCreatedEnhanced",
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
            {"indexed": True, "internalType": "address", "name": "creator", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "tournamentName", "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "entryFee", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "startTime", "type": "uint256"}
        ],
        "name": "TournamentCreatedEnhanced",
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
            {"indexed": True, "internalType": "address", "name": "winner", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "winnerFarcasterFid", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "pot", "type": "uint256"}
        ],
        "name": "TournamentEndedEnhanced",
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
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "tournamentId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "participant", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "farcasterFid", "type": "uint256"}
        ],
        "name": "TournamentJoinedEnhanced",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "buyer", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "toursAmount", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "monAmount", "type": "uint256"}
        ],
        "name": "ToursPurchased",
        "type": "event"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "newUsername", "type": "string"},
            {"internalType": "string", "name": "newBio", "type": "string"}
        ],
        "name": "updateFarcasterProfile",
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
        "name": "commentFee",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "farcasterFidToAddress",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
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
        "inputs": [
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"}
        ],
        "name": "getJournalEntriesByFarcasterFid",
        "outputs": [
            {"internalType": "uint256[]", "name": "", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "entryId", "type": "uint256"}
        ],
        "name": "getJournalEntry",
        "outputs": [
            {"internalType": "address", "name": "author", "type": "address"},
            {"internalType": "string", "name": "contentHash", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"internalType": "string", "name": "farcasterCastHash", "type": "string"},
            {"internalType": "string", "name": "location", "type": "string"},
            {"internalType": "string", "name": "difficulty", "type": "string"},
            {"internalType": "bool", "name": "isSharedOnFarcaster", "type": "bool"}
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
        "inputs": [
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"}
        ],
        "name": "getLocationsByFarcasterFid",
        "outputs": [
            {"internalType": "uint256[]", "name": "", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"}
        ],
        "name": "getProfileByFarcasterFid",
        "outputs": [
            {"internalType": "address", "name": "userAddress", "type": "address"},
            {"internalType": "bool", "name": "exists", "type": "bool"},
            {"internalType": "uint256", "name": "journalCount", "type": "uint256"},
            {"internalType": "string", "name": "farcasterUsername", "type": "string"},
            {"internalType": "string", "name": "farcasterBio", "type": "string"},
            {"internalType": "uint256", "name": "createdAt", "type": "uint256"}
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
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "name": "journalComments",
        "outputs": [
            {"internalType": "address", "name": "commenter", "type": "address"},
            {"internalType": "string", "name": "contentHash", "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"internalType": "string", "name": "farcasterCastHash", "type": "string"}
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
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"internalType": "string", "name": "farcasterCastHash", "type": "string"},
            {"internalType": "string", "name": "location", "type": "string"},
            {"internalType": "string", "name": "difficulty", "type": "string"},
            {"internalType": "bool", "name": "isSharedOnFarcaster", "type": "bool"}
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
        "name": "LEGACY_FEE_PERCENT",
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
        "inputs": [],
        "name": "profileFee",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
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
            {"internalType": "uint256", "name": "journalCount", "type": "uint256"},
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"internalType": "string", "name": "farcasterUsername", "type": "string"},
            {"internalType": "string", "name": "farcasterBio", "type": "string"},
            {"internalType": "uint256", "name": "createdAt", "type": "uint256"}
        ],
        "stateMutability": "view",
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
            {"internalType": "uint256", "name": "startTime", "type": "uint256"},
            {"internalType": "uint256", "name": "farcasterFid", "type": "uint256"},
            {"internalType": "string", "name": "farcasterCastHash", "type": "string"},
            {"internalType": "string", "name": "tournamentName", "type": "string"},
            {"internalType": "string", "name": "description", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "TOURS_PRICE",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "TOURS_REWARD",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
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
                    },
                    {
                        "constant": True,
                        "inputs": [
                            {"name": "_owner", "type": "address"},
                            {"name": "_spender", "type": "address"}
                        ],
                        "name": "allowance",
                        "outputs": [{"name": "", "type": "uint256"}],
                        "type": "function"
                    }
                ]

                # Initialize contracts
                contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)
                tours_contract = w3.eth.contract(address=Web3.to_checksum_address(TOURS_TOKEN_ADDRESS), abi=TOURS_ABI)
                logger.info("Contracts initialized successfully")
                return True
            else:
                logger.warning(f"Web3 connection failed on attempt {attempt}/{retries}")
                time.sleep(5)
        except Exception as e:
            logger.error(f"Error connecting to Web3 on attempt {attempt}/{retries}: {str(e)}")
            if attempt < retries:
                time.sleep(5)
    logger.error("All Web3 connection attempts failed. Proceeding without blockchain functionality.")
    w3 = None
    contract = None
    tours_contract = None
    return False

# Initialize Web3 and contracts
initialize_web3()

# Initialize SQLite database
conn = sqlite3.connect('empowertours.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        user_id TEXT PRIMARY KEY,
        session_id TEXT,
        wallet_address TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS pending_txs (
        user_id TEXT,
        tx_type TEXT,
        tx_data TEXT,
        name TEXT,
        difficulty TEXT,
        latitude INTEGER,
        longitude INTEGER,
        photo_hash TEXT,
        location_id INTEGER,
        tournament_id INTEGER
    )
''')
conn.commit()

async def get_gas_fees(wallet_address):
    if not w3:
        logger.error("Web3 not available for gas fee calculation")
        return {
            'maxFeePerGas': 2 * 10**9,  # 2 gwei fallback
            'maxPriorityFeePerGas': 1 * 10**9  # 1 gwei fallback
        }
    try:
        base_fee = w3.eth.get_block('latest')['baseFeePerGas']
        max_priority_fee = w3.eth.max_priority_fee
        max_fee_per_gas = base_fee + max_priority_fee
        return {
            'maxFeePerGas': max_fee_per_gas,
            'maxPriorityFeePerGas': max_priority_fee
        }
    except Exception as e:
        logger.error(f"Error fetching gas fees for {wallet_address}: {str(e)}")
        return {
            'maxFeePerGas': 2 * 10**9,
            'maxPriorityFeePerGas': 1 * 10**9
        }

async def create_profile_tx(wallet_address, user):
    if not w3 or not contract:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        profile = contract.functions.profiles(wallet_address).call()
        if profile[0]:
            return {'status': 'error', 'message': f"Profile already exists for {wallet_address}! Try /journal or /buildaclimb. 🪨"}
        
        profile_fee = contract.functions.profileFee().call()
        balance = w3.eth.get_balance(wallet_address)
        
        # Simulate createProfile transaction
        try:
            w3.eth.call({
                'from': wallet_address,
                'to': CONTRACT_ADDRESS,
                'data': contract.encodeABI(fn_name='createProfile', args=[])
            })
        except ContractLogicError as e:
            logger.error(f"Simulation error in createProfile: {str(e)}")
            return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the contract is valid. 😅"}
        
        gas_estimate = contract.functions.createProfile().estimate_gas({'from': wallet_address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = await get_gas_fees(wallet_address)
        gas_cost = gas_limit * gas_fees['maxFeePerGas']
        
        if balance < gas_cost + profile_fee:
            return {
                'status': 'error',
                'message': (
                    f"Need {w3.from_wei(profile_fee + gas_cost, 'ether')} $MON to create profile. "
                    f"Your balance: {w3.from_wei(balance, 'ether')} $MON. "
                    "Top up at <a href=\"https://testnet.monad.xyz/faucet\">Monad Faucet</a>! 🪙"
                )
            }
        
        # Build createProfile transaction
        nonce = w3.eth.get_transaction_count(wallet_address)
        create_tx = contract.functions.createProfile().build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        
        # Build payment transaction to OWNER_ADDRESS
        payment_tx = {
            'chainId': 10143,
            'from': wallet_address,
            'to': OWNER_ADDRESS,
            'value': profile_fee,
            'nonce': nonce + 1,
            'gas': 21000,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        }
        
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data) VALUES (?, ?, ?)",
            (str(user.id), 'create_profile', json.dumps(create_tx))
        )
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data) VALUES (?, ?, ?)",
            (str(user.id), 'payment_to_owner', json.dumps(payment_tx))
        )
        conn.commit()
        return {
            'status': 'success',
            'tx_type': 'create_profile',
            'tx_data': create_tx,
            'next_tx': {'type': 'payment_to_owner', 'tx_data': payment_tx}
        }
    except ContractLogicError as e:
        logger.error(f"Contract error in createProfile: {str(e)}")
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the contract is valid or try again later. 😅"}
    except Exception as e:
        logger.error(f"Error in create_profile_tx: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def add_journal_entry_tx(wallet_address, content_hash, user):
    if not w3 or not contract:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        profile = contract.functions.profiles(wallet_address).call()
        if not profile[0]:
            return {'status': 'error', 'message': "You need to create a profile first with /createprofile! 🪙"}
        
        try:
            w3.eth.call({
                'from': wallet_address,
                'to': CONTRACT_ADDRESS,
                'data': contract.encodeABI(fn_name='addJournalEntry', args=[content_hash])
            })
        except ContractLogicError as e:
            logger.error(f"Simulation error in addJournalEntry: {str(e)}")
            return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure you have a profile. 😅"}
        
        gas_estimate = contract.functions.addJournalEntry(content_hash).estimate_gas({'from': wallet_address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = await get_gas_fees(wallet_address)
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.addJournalEntry(content_hash).build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data) VALUES (?, ?, ?)",
            (str(user.id), 'journal_entry', json.dumps(tx))
        )
        conn.commit()
        return {'status': 'success', 'tx_type': 'journal_entry', 'tx_data': tx}
    except ContractLogicError as e:
        logger.error(f"Contract error in addJournalEntry: {str(e)}")
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure you have a profile and try again. 😅"}
    except Exception as e:
        logger.error(f"Error in add_journal_entry_tx: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def add_comment_tx(wallet_address, entry_id, comment, user):
    if not w3 or not contract:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        profile = contract.functions.profiles(wallet_address).call()
        if not profile[0]:
            return {'status': 'error', 'message': "You need to create a profile first with /createprofile! 🪙"}
        
        comment_hash = w3.keccak(text=comment).hex()
        comment_fee = contract.functions.commentFee().call()
        balance = w3.eth.get_balance(wallet_address)
        try:
            w3.eth.call({
                'from': wallet_address,
                'to': CONTRACT_ADDRESS,
                'value': comment_fee,
                'data': contract.encodeABI(fn_name='addComment', args=[entry_id, comment_hash])
            })
        except ContractLogicError as e:
            logger.error(f"Simulation error in addComment: {str(e)}")
            return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the entry exists. 😅"}
        
        gas_estimate = contract.functions.addComment(entry_id, comment_hash).estimate_gas({
            'from': wallet_address,
            'value': comment_fee
        })
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = await get_gas_fees(wallet_address)
        gas_cost = gas_limit * gas_fees['maxFeePerGas']
        
        if balance < gas_cost + comment_fee:
            return {
                'status': 'error',
                'message': (
                    f"Need {w3.from_wei(comment_fee + gas_cost, 'ether')} $MON to comment. "
                    f"Your balance: {w3.from_wei(balance, 'ether')} $MON. "
                    "Top up at <a href=\"https://testnet.monad.xyz/faucet\">Monad Faucet</a>! 🪙"
                )
            }
        
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.addComment(entry_id, comment_hash).build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'value': comment_fee,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data, location_id) VALUES (?, ?, ?, ?)",
            (str(user.id), 'add_comment', json.dumps(tx), entry_id)
        )
        conn.commit()
        return {'status': 'success', 'tx_type': 'add_comment', 'tx_data': tx}
    except ContractLogicError as e:
        logger.error(f"Contract error in addComment: {str(e)}")
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the entry exists and you have enough $MON. 😅"}
    except Exception as e:
        logger.error(f"Error in add_comment_tx: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def create_climbing_location_tx(wallet_address, name, difficulty, latitude, longitude, photo_hash, user):
    if not w3 or not contract or not tours_contract:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        profile = contract.functions.profiles(wallet_address).call()
        if not profile[0]:
            return {'status': 'error', 'message': "You need to create a profile first with /createprofile! 🪙"}
        
        if not name or not difficulty:
            return {'status': 'error', 'message': "Name and difficulty cannot be empty! 😅"}
        
        location_cost = contract.functions.locationCreationCost().call()
        balance = tours_contract.functions.balanceOf(wallet_address).call()
        allowance = tours_contract.functions.allowance(wallet_address, CONTRACT_ADDRESS).call()
        if balance < location_cost:
            return {
                'status': 'error',
                'message': (
                    f"Need {location_cost/10**18} $TOURS to create a climb. "
                    f"Your balance: {balance/10**18} $TOURS. Top up your wallet! 🪙"
                )
            }
        if allowance < location_cost:
            gas_fees = await get_gas_fees(wallet_address)
            nonce = w3.eth.get_transaction_count(wallet_address)
            approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, location_cost).build_transaction({
                'chainId': 10143,
                'from': wallet_address,
                'nonce': nonce,
                'gas': 100000,
                'maxFeePerGas': gas_fees['maxFeePerGas'],
                'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
            })
            cursor.execute(
                "INSERT INTO pending_txs (user_id, tx_type, tx_data, name, difficulty, latitude, longitude, photo_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(user.id), 'approve_tours', json.dumps(approve_tx), name, difficulty, latitude, longitude, photo_hash)
            )
            conn.commit()
            return {
                'status': 'success',
                'tx_type': 'approve_tours',
                'tx_data': approve_tx,
                'next_tx': {
                    'type': 'create_climbing_location',
                    'name': name,
                    'difficulty': difficulty,
                    'latitude': latitude,
                    'longitude': longitude,
                    'photo_hash': photo_hash
                }
            }
        
        try:
            w3.eth.call({
                'from': wallet_address,
                'to': CONTRACT_ADDRESS,
                'data': contract.encodeABI(
                    fn_name='createClimbingLocation',
                    args=[name, difficulty, latitude, longitude, photo_hash]
                )
            })
        except ContractLogicError as e:
            logger.error(f"Simulation error in createClimbingLocation: {str(e)}")
            return {'status': 'error', 'message': f"Contract error: {str(e)}. Check parameters or contract state. 😅"}
        
        gas_estimate = contract.functions.createClimbingLocation(
            name, difficulty, latitude, longitude, photo_hash
        ).estimate_gas({'from': wallet_address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = await get_gas_fees(wallet_address)
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.createClimbingLocation(
            name, difficulty, latitude, longitude, photo_hash
        ).build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data, name, difficulty, latitude, longitude, photo_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(user.id), 'create_climbing_location', json.dumps(tx), name, difficulty, latitude, longitude, photo_hash)
        )
        conn.commit()
        return {'status': 'success', 'tx_type': 'create_climbing_location', 'tx_data': tx}
    except ContractLogicError as e:
        logger.error(f"Contract error in createClimbingLocation: {str(e)}")
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure you have a profile and sufficient $TOURS allowance. 😅"}
    except Exception as e:
        logger.error(f"Error in create_climbing_location_tx: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def purchase_climbing_location_tx(wallet_address, location_id, user):
    if not w3 or not contract or not tours_contract:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        profile = contract.functions.profiles(wallet_address).call()
        if not profile[0]:
            return {'status': 'error', 'message': "You need to create a profile first with /createprofile! 🪙"}
        
        location_cost = contract.functions.locationCreationCost().call()
        balance = tours_contract.functions.balanceOf(wallet_address).call()
        allowance = tours_contract.functions.allowance(wallet_address, CONTRACT_ADDRESS).call()
        if balance < location_cost:
            return {
                'status': 'error',
                'message': (
                    f"Need {location_cost/10**18} $TOURS to purchase a climb. "
                    f"Your balance: {balance/10**18} $TOURS. Top up your wallet! 🪙"
                )
            }
        if allowance < location_cost:
            gas_fees = await get_gas_fees(wallet_address)
            nonce = w3.eth.get_transaction_count(wallet_address)
            approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, location_cost).build_transaction({
                'chainId': 10143,
                'from': wallet_address,
                'nonce': nonce,
                'gas': 100000,
                'maxFeePerGas': gas_fees['maxFeePerGas'],
                'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
            })
            cursor.execute(
                "INSERT INTO pending_txs (user_id, tx_type, tx_data, location_id) VALUES (?, ?, ?, ?)",
                (str(user.id), 'approve_tours', json.dumps(approve_tx), location_id)
            )
            conn.commit()
            return {
                'status': 'success',
                'tx_type': 'approve_tours',
                'tx_data': approve_tx,
                'next_tx': {
                    'type': 'purchase_climbing_location',
                    'location_id': location_id
                }
            }
        
        try:
            w3.eth.call({
                'from': wallet_address,
                'to': CONTRACT_ADDRESS,
                'data': contract.encodeABI(
                    fn_name='purchaseClimbingLocation',
                    args=[location_id]
                )
            })
        except ContractLogicError as e:
            logger.error(f"Simulation error in purchaseClimbingLocation: {str(e)}")
            return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the location ID is valid. 😅"}
        
        gas_estimate = contract.functions.purchaseClimbingLocation(location_id).estimate_gas({'from': wallet_address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = await get_gas_fees(wallet_address)
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.purchaseClimbingLocation(location_id).build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data, location_id) VALUES (?, ?, ?, ?)",
            (str(user.id), 'purchase_climbing_location', json.dumps(tx), location_id)
        )
        conn.commit()
        return {'status': 'success', 'tx_type': 'purchase_climbing_location', 'tx_data': tx}
    except ContractLogicError as e:
        logger.error(f"Contract error in purchaseClimbingLocation: {str(e)}")
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the location ID is valid. 😅"}
    except Exception as e:
        logger.error(f"Error in purchase_climbing_location_tx: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def create_tournament_tx(wallet_address, entry_fee, user):
    if not w3 or not contract:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        profile = contract.functions.profiles(wallet_address).call()
        if not profile[0]:
            return {'status': 'error', 'message': "You need to create a profile first with /createprofile! 🪙"}
        
        try:
            w3.eth.call({
                'from': wallet_address,
                'to': CONTRACT_ADDRESS,
                'data': contract.encodeABI(
                    fn_name='createTournament',
                    args=[entry_fee]
                )
            })
        except ContractLogicError as e:
            logger.error(f"Simulation error in createTournament: {str(e)}")
            return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure you have a profile. 😅"}
        
        gas_estimate = contract.functions.createTournament(entry_fee).estimate_gas({'from': wallet_address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = await get_gas_fees(wallet_address)
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.createTournament(entry_fee).build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data) VALUES (?, ?, ?)",
            (str(user.id), 'create_tournament', json.dumps(tx))
        )
        conn.commit()
        return {'status': 'success', 'tx_type': 'create_tournament', 'tx_data': tx}
    except ContractLogicError as e:
        logger.error(f"Contract error in createTournament: {str(e)}")
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure you have a profile. 😅"}
    except Exception as e:
        logger.error(f"Error in create_tournament_tx: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def join_tournament_tx(wallet_address, tournament_id, user):
    if not w3 or not contract or not tours_contract:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        profile = contract.functions.profiles(wallet_address).call()
        if not profile[0]:
            return {'status': 'error', 'message': "You need to create a profile first with /createprofile! 🪙"}
        
        tournament = contract.functions.tournaments(tournament_id).call()
        entry_fee = tournament[0]
        balance = tours_contract.functions.balanceOf(wallet_address).call()
        allowance = tours_contract.functions.allowance(wallet_address, CONTRACT_ADDRESS).call()
        if balance < entry_fee:
            return {
                'status': 'error',
                'message': (
                    f"Need {entry_fee/10**18} $TOURS to join tournament. "
                    f"Your balance: {balance/10**18} $TOURS. Top up your wallet! 🪙"
                )
            }
        if allowance < entry_fee:
            gas_fees = await get_gas_fees(wallet_address)
            nonce = w3.eth.get_transaction_count(wallet_address)
            approve_tx = tours_contract.functions.approve(CONTRACT_ADDRESS, entry_fee).build_transaction({
                'chainId': 10143,
                'from': wallet_address,
                'nonce': nonce,
                'gas': 100000,
                'maxFeePerGas': gas_fees['maxFeePerGas'],
                'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
            })
            cursor.execute(
                "INSERT INTO pending_txs (user_id, tx_type, tx_data, tournament_id) VALUES (?, ?, ?, ?)",
                (str(user.id), 'approve_tours', json.dumps(approve_tx), tournament_id)
            )
            conn.commit()
            return {
                'status': 'success',
                'tx_type': 'approve_tours',
                'tx_data': approve_tx,
                'next_tx': {
                    'type': 'join_tournament',
                    'tournament_id': tournament_id
                }
            }
        
        try:
            w3.eth.call({
                'from': wallet_address,
                'to': CONTRACT_ADDRESS,
                'data': contract.encodeABI(
                    fn_name='joinTournament',
                    args=[tournament_id]
                )
            })
        except ContractLogicError as e:
            logger.error(f"Simulation error in joinTournament: {str(e)}")
            return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the tournament ID is valid. 😅"}
        
        gas_estimate = contract.functions.joinTournament(tournament_id).estimate_gas({'from': wallet_address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = await get_gas_fees(wallet_address)
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.joinTournament(tournament_id).build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data, tournament_id) VALUES (?, ?, ?, ?)",
            (str(user.id), 'join_tournament', json.dumps(tx), tournament_id)
        )
        conn.commit()
        return {'status': 'success', 'tx_type': 'join_tournament', 'tx_data': tx}
    except ContractLogicError as e:
        logger.error(f"Contract error in joinTournament: {str(e)}")
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the tournament ID is valid. 😅"}
    except Exception as e:
        logger.error(f"Error in join_tournament_tx: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def end_tournament_tx(wallet_address, tournament_id, winner_address, user):
    if not w3 or not contract:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        if wallet_address.lower() != OWNER_ADDRESS.lower():
            return {'status': 'error', 'message': "Only the owner can end tournaments! 🚫"}
        if not w3.is_address(winner_address):
            return {'status': 'error', 'message': "Invalid winner address! 😕"}
        
        try:
            w3.eth.call({
                'from': wallet_address,
                'to': CONTRACT_ADDRESS,
                'data': contract.encodeABI(
                    fn_name='endTournament',
                    args=[tournament_id, winner_address]
                )
            })
        except ContractLogicError as e:
            logger.error(f"Simulation error in endTournament: {str(e)}")
            return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the tournament ID is valid. 😅"}
        
        gas_estimate = contract.functions.endTournament(tournament_id, winner_address).estimate_gas({'from': wallet_address})
        gas_limit = int(gas_estimate * 1.2)
        gas_fees = await get_gas_fees(wallet_address)
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.endTournament(tournament_id, winner_address).build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        cursor.execute(
            "INSERT INTO pending_txs (user_id, tx_type, tx_data, tournament_id) VALUES (?, ?, ?, ?)",
            (str(user.id), 'end_tournament', json.dumps(tx), tournament_id)
        )
        conn.commit()
        return {'status': 'success', 'tx_type': 'end_tournament', 'tx_data': tx}
    except ContractLogicError as e:
        logger.error(f"Contract error in endTournament: {str(e)}")
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the tournament ID is valid. 😅"}
    except Exception as e:
        logger.error(f"Error in end_tournament_tx: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def get_climbing_locations():
    if not w3 or not contract:
        return []
    try:
        location_count = contract.functions.getClimbingLocationCount().call()
        tour_list = []
        for i in range(location_count):
            location = contract.functions.climbingLocations(i).call()
            tour_list.append(
                f"🏔️ {location[1]} ({location[2]}) - By {location[0][:6]}...\n"
                f"   Location: ({location[3]/10**6:.4f}, {location[4]/10**6:.4f})\n"
                f"   Map: https://www.google.com/maps?q={location[3]/10**6},{location[4]/10**6}"
            )
        return tour_list
    except Exception as e:
        logger.error(f"Error in get_climbing_locations: {str(e)}")
        return []

async def broadcast_transaction(signed_tx_hex, pending_tx, user, context):
    if not w3:
        return {'status': 'error', 'message': "Blockchain connection unavailable. Try again later! 😅"}
    try:
        tx_hash = w3.eth.send_raw_transaction(signed_tx_hex)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        cursor.execute("DELETE FROM pending_txs WHERE user_id = ? AND tx_type = ?", (str(user.id), pending_tx['tx_type']))
        conn.commit()
        
        if receipt.status == 1:
            if pending_tx['tx_type'] == 'create_profile':
                cursor.execute("UPDATE sessions SET wallet_address = ? WHERE user_id = ?", (pending_tx['wallet_address'], str(user.id)))
                conn.commit()
                return {
                    'status': 'success',
                    'message': (
                        f"Welcome aboard, {user.first_name}! Your profile is live! 🎉 Tx: {tx_hash.hex()}\n"
                        "Try /journal to log your first climb or /buildaclimb to share a spot! 🪨"
                    ),
                    'group_message': f"New climber {user.username or user.first_name} joined EmpowerTours! 🧗 Tx: {tx_hash.hex()}"
                }
            elif pending_tx['tx_type'] == 'payment_to_owner':
                return {
                    'status': 'success',
                    'message': f"Payment to owner successful! Your profile is fully activated! 🎉 Tx: {tx_hash.hex()}",
                    'group_message': f"{user.username or user.first_name} completed profile payment! 🪙 Tx: {tx_hash.hex()}"
                }
            elif pending_tx['tx_type'] == 'journal_entry':
                return {
                    'status': 'success',
                    'message': f"Journal entry logged, {user.first_name}! You earned 5 $TOURS! 🎉 Tx: {tx_hash.hex()}",
                    'group_message': f"{user.username or user.first_name} shared a climb journal! 🪨 Check it out! Tx: {tx_hash.hex()}"
                }
            elif pending_tx['tx_type'] == 'approve_tours' and 'next_tx' in pending_tx:
                next_tx_type = pending_tx['next_tx']['type']
                gas_fees = await get_gas_fees(pending_tx['wallet_address'])
                nonce = w3.eth.get_transaction_count(pending_tx['wallet_address'])
                if next_tx_type == 'create_climbing_location':
                    next_tx = contract.functions.createClimbingLocation(
                        pending_tx['next_tx']['name'],
                        pending_tx['next_tx']['difficulty'],
                        pending_tx['next_tx']['latitude'],
                        pending_tx['next_tx']['longitude'],
                        pending_tx['next_tx']['photo_hash']
                    ).build_transaction({
                        'chainId': 10143,
                        'from': pending_tx['wallet_address'],
                        'nonce': nonce,
                        'gas': 200000,
                        'maxFeePerGas': gas_fees['maxFeePerGas'],
                        'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
                    })
                    cursor.execute(
                        "INSERT INTO pending_txs (user_id, tx_type, tx_data, name, difficulty, latitude, longitude, photo_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(user.id), 'create_climbing_location', json.dumps(next_tx), 
                         pending_tx['next_tx']['name'], pending_tx['next_tx']['difficulty'],
                         pending_tx['next_tx']['latitude'], pending_tx['next_tx']['longitude'],
                         pending_tx['next_tx']['photo_hash'])
                    )
                    conn.commit()
                    return {
                        'status': 'success',
                        'message': (
                            f"$TOURS approval successful! Please send the signed transaction hash for climb creation (10 $TOURS) using your wallet."
                        ),
                        'tx_type': 'create_climbing_location',
                        'tx_data': next_tx
                    }
                elif next_tx_type == 'purchase_climbing_location':
                    next_tx = contract.functions.purchaseClimbingLocation(
                        pending_tx['next_tx']['location_id']
                    ).build_transaction({
                        'chainId': 10143,
                        'from': pending_tx['wallet_address'],
                        'nonce': nonce,
                        'gas': 100000,
                        'maxFeePerGas': gas_fees['maxFeePerGas'],
                        'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
                    })
                    cursor.execute(
                        "INSERT INTO pending_txs (user_id, tx_type, tx_data, location_id) VALUES (?, ?, ?, ?)",
                        (str(user.id), 'purchase_climbing_location', json.dumps(next_tx), pending_tx['next_tx']['location_id'])
                    )
                    conn.commit()
                    return {
                        'status': 'success',
                        'message': (
                            f"$TOURS approval successful! Please send the signed transaction hash for climb purchase (10 $TOURS) using your wallet."
                        ),
                        'tx_type': 'purchase_climbing_location',
                        'tx_data': next_tx
                    }
                elif next_tx_type == 'join_tournament':
                    next_tx = contract.functions.joinTournament(
                        pending_tx['next_tx']['tournament_id']
                    ).build_transaction({
                        'chainId': 10143,
                        'from': pending_tx['wallet_address'],
                        'nonce': nonce,
                        'gas': 100000,
                        'maxFeePerGas': gas_fees['maxFeePerGas'],
                        'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
                    })
                    cursor.execute(
                        "INSERT INTO pending_txs (user_id, tx_type, tx_data, tournament_id) VALUES (?, ?, ?, ?)",
                        (str(user.id), 'join_tournament', json.dumps(next_tx), pending_tx['next_tx']['tournament_id'])
                    )
                    conn.commit()
                    return {
                        'status': 'success',
                        'message': (
                            f"$TOURS approval successful! Please send the signed transaction hash for joining tournament using your wallet."
                        ),
                        'tx_type': 'join_tournament',
                        'tx_data': next_tx
                    }
            elif pending_tx['tx_type'] == 'create_climbing_location':
                location_id = contract.functions.getClimbingLocationCount().call() - 1
                location = contract.functions.climbingLocations(location_id).call()
                return {
                    'status': 'success',
                    'message': (
                        f"Climb created, {user.first_name}! 🪨 {pending_tx['name']} ({pending_tx['difficulty']}) "
                        f"at ({location[3]/10**6:.4f}, {location[4]/10**6:.4f}). Tx: {tx_hash.hex()}"
                    ),
                    'group_message': (
                        f"New climb by {user.username or user.first_name}! 🧗\n"
                        f"Name: {pending_tx['name']} ({pending_tx['difficulty']})\n"
                        f"Location: ({location[3]/10**6:.4f}, {location[4]/10**6:.4f})\n"
                        f"Tx: {tx_hash.hex()}"
                    )
                }
            elif pending_tx['tx_type'] == 'purchase_climbing_location':
                return {
                    'status': 'success',
                    'message': f"Climb #{pending_tx['location_id']} purchased, {user.first_name}! 🎉 Tx: {tx_hash.hex()}",
                    'group_message': f"{user.username or user.first_name} purchased climb #{pending_tx['location_id']}! 🪨 Tx: {tx_hash.hex()}"
                }
            elif pending_tx['tx_type'] == 'add_comment':
                return {
                    'status': 'success',
                    'message': f"Comment added to entry #{pending_tx['location_id']}, {user.first_name}! 🎉 Tx: {tx_hash.hex()}",
                    'group_message': f"{user.username or user.first_name} commented on journal entry #{pending_tx['location_id']}! 🗣️ Tx: {tx_hash.hex()}"
                }
            elif pending_tx['tx_type'] == 'create_tournament':
                tournament_id = contract.functions.getTournamentCount().call() - 1
                return {
                    'status': 'success',
                    'message': f"Tournament #{tournament_id} created, {user.first_name}! 🏆 Tx: {tx_hash.hex()}",
                    'group_message': (
                        f"New tournament #{tournament_id} by {user.username or user.first_name}! 🏆\n"
                        f"Join with /jointournament {tournament_id}\n"
                        f"Tx: {tx_hash.hex()}"
                    )
                }
            elif pending_tx['tx_type'] == 'join_tournament':
                return {
                    'status': 'success',
                    'message': f"Joined tournament #{pending_tx['tournament_id']}, {user.first_name}! 🏆 Tx: {tx_hash.hex()}",
                    'group_message': f"{user.username or user.first_name} joined tournament #{pending_tx['tournament_id']}! 🏆 Tx: {tx_hash.hex()}"
                }
            elif pending_tx['tx_type'] == 'end_tournament':
                return {
                    'status': 'success',
                    'message': f"Tournament #{pending_tx['tournament_id']} ended, {user.first_name}! 🏆 Tx: {tx_hash.hex()}",
                    'group_message': f"Tournament #{pending_tx['tournament_id']} ended by {user.username or user.first_name}! 🏆 Tx: {tx_hash.hex()}"
                }
        else:
            return {'status': 'error', 'message': "Transaction failed. Ensure the signed transaction is valid and try again! 💪"}
    except Exception as e:
        logger.error(f"Error in broadcast_transaction: {str(e)}")
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}
