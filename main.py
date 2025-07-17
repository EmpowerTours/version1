import logging
import os
import signal
import asyncio
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, FileResponse
from contextlib import asynccontextmanager
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity, ReplyKeyboardMarkup, KeyboardButton, BotCommand
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
import asyncpg  # Added for Postgres
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
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
TOURS_TOKEN_ADDRESS = os.getenv("TOURS_TOKEN_ADDRESS")
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS")
LEGACY_ADDRESS = os.getenv("LEGACY_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_CONNECT_PROJECT_ID = os.getenv("WALLET_CONNECT_PROJECT_ID")
EXPLORER_URL = "https://testnet.monadexplorer.com"
DATABASE_URL = os.getenv("DATABASE_URL")

# Log environment variables
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
logger.info(f"DATABASE_URL: {'Set' if DATABASE_URL else 'Missing'}")
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
if not DATABASE_URL: missing_vars.append("DATABASE_URL")
if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
    logger.warning("Proceeding with limited functionality")
else:
    logger.info("All required environment variables are set")

# Contract ABIs (unchanged)
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
        "name": "TournamentCreatedEmbedded",
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

# Global blockchain variables
w3 = None
contract = None
tours_contract = None
pool = None
sessions = {}
pending_wallets = {}
journal_data = {}
reverse_sessions = {}  # wallet: user_id mapping for event PMs
webhook_failed = False
last_processed_block = 0
processed_updates = set()  # To prevent duplicate processing
climb_cache = None  # Cache for climbs
journal_cache = None  # Cache for journals
cache_timestamp = 0
CACHE_TTL = 300  # 5 minutes

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
async def initialize_web3():
    global w3, contract, tours_contract
    if not MONAD_RPC_URL or not CONTRACT_ADDRESS or not TOURS_TOKEN_ADDRESS:
        logger.error("Cannot initialize Web3: missing blockchain-related environment variables")
        return False
    try:
        w3 = AsyncWeb3(AsyncHTTPProvider(MONAD_RPC_URL))
        is_connected = await w3.is_connected()
        if is_connected:
            logger.info("AsyncWeb3 initialized successfully")
            contract = w3.eth.contract(address=w3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)
            tours_contract = w3.eth.contract(address=w3.to_checksum_address(TOURS_TOKEN_ADDRESS), abi=TOURS_ABI)
            logger.info("Contracts initialized successfully")
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
            f"Welcome to EmpowerTours! 🧗\n"
            f"Join our community at [EmpowerTours Chat](https://t.me/empowertourschat) to connect with climbers and explore Web3-powered adventures.\n"
            f"Use /connectwallet to link your wallet, then /createprofile to get started.\n"
            f"Run /tutorial for a full guide or /help for all commands."
        )
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        logger.info(f"Sent /start response to user {update.effective_user.id}: {welcome_message}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /start for user {update.effective_user.id}: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again or contact support at https://t.me/empowertourschat. 😅")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /ping command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        webhook_ok = await check_webhook()
        status = "Webhook OK" if webhook_ok else "Webhook failed, using polling"
        await update.message.reply_text(f"Pong! Bot is running. {status}. Try /start or /createprofile.")
        logger.info(f"Sent /ping response to user {update.effective_user.id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /ping: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

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
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

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
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /debug command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        webhook_ok = await check_webhook()
        if webhook_ok:
            await update.effective_message.reply_text("Webhook is correctly set to https://version1-production.up.railway.app/webhook")
        else:
            await update.effective_message.reply_text("Webhook is not correctly set. Use /forcewebhook to reset or check logs.")
        logger.info(f"Sent /debug response to user {update.effective_user.id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /debug: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.effective_message.reply_text(f"Error: {str(e)}. Try again! 😅")

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
            "**Tutorial**\n"
            "1. Wallet:\n"
            "- Get MetaMask, Phantom, or Gnosis Safe.\n"
            "- Add Monad testnet (RPC: https://testnet-rpc.monad.xyz, ID: 10143).\n"
            "- If you see a chain ID mismatch (e.g., 10159), go to MetaMask Settings > Networks, remove all Monad Testnet entries, and reconnect.\n"
            "- Get $MON: https://testnet.monad.xyz/faucet\n\n"
            "2. Connect:\n"
            "- Use /connectwallet to connect via MetaMask or WalletConnect\n\n"
            "3. Profile:\n"
            "- /createprofile (1 $MON, receive 1 $TOURS)\n\n"
            "4. Manage Tokens:\n"
            "- /buyTours amount - Buy $TOURS tokens with $MON (e.g., /buyTours 10 to buy 10 $TOURS)\n"
            "- /sendTours recipient amount - Send $TOURS to another wallet (e.g., /sendTours 0x123...456 10 to send 10 $TOURS)\n\n"
            "5. Explore:\n"
            "- /journal your journal entry - Log a climb (5 $TOURS)\n"
            "- /comment id your comment - Comment on a journal (0.1 $MON)\n"
            "- /buildaclimb name difficulty - Create a climb (10 $TOURS)\n"
            "- /purchaseclimb id - Buy a climb (10 $TOURS)\n"
            "- /findaclimb - List available climbs\n"
            "- /journals - List all journal entries\n"
            "- /viewjournal id - View a journal entry and its comments\n"
            "- /viewclimb id - View a specific climb\n"
            "- /mypurchases - View your purchased climbs\n"
            "- /createtournament fee - Start a tournament with an entry fee in $TOURS (e.g., /createtournament 10 for 10 $TOURS per participant)\n"
            "- /tournaments - List all tournaments with IDs and participant counts\n"
            "- /jointournament id - Join a tournament by paying the entry fee\n"
            "- /endtournament id winner - End a tournament (owner only) and award the prize to the winner’s wallet address (e.g., /endtournament 1 0x5fE8373C839948bFCB707A8a8A75A16E2634A725)\n"
            "- /balance - Check your $MON and $TOURS balance\n"
            "- /help - List all commands\n"
            "Join our community at [EmpowerTours Chat](https://t.me/empowertourschat)! Try /connectwallet!"
        )
        await update.message.reply_text(tutorial_text, parse_mode="Markdown")
        logger.info(f"Sent /tutorial response to user {update.effective_user.id}: {tutorial_text}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /tutorial for user {update.effective_user.id}: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error in tutorial: {str(e)}. Try again or use /help! 😅")

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /help command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        help_text = (
            "**EmpowerTours Commands**\n"
            "/start - Welcome message\n\n"
            "/tutorial - Setup guide\n\n"
            "/connectwallet - Connect your wallet (use chain ID 10143; remove incorrect Monad Testnet entries from MetaMask if needed)\n\n"
            "/createprofile - Create profile (1 $MON, receive 1 $TOURS)\n\n"
            "/buyTours amount - Buy $TOURS tokens with $MON (e.g., /buyTours 10 to buy 10 $TOURS)\n\n"
            "/sendTours recipient amount - Send $TOURS to another wallet (e.g., /sendTours 0x123...456 10 to send 10 $TOURS)\n\n"
            "/journal entry - Log a climb for an existing climb with photos or notes (5 $TOURS)\n\n"
            "/buildaclimb name difficulty - Create a new climb with name, difficulty, and optional photo/location (10 $TOURS)\n\n"
            "/comment id comment - Comment on a journal (0.1 $MON)\n\n"
            "/purchaseclimb id - Buy a climb (10 $TOURS)\n\n"
            "/findaclimb - List available climbs\n\n"
            "/journals - List all journal entries\n\n"
            "/viewjournal id - View a journal entry and its comments\n\n"
            "/viewclimb id - View a specific climb\n\n"
            "/mypurchases - View your purchased climbs\n\n"
            "/createtournament fee - Start a tournament with an entry fee in $TOURS (e.g., /createtournament 10 sets a 10 $TOURS fee per participant)\n\n"
            "/tournaments - List all tournaments with IDs and participant counts\n\n"
            "/jointournament id - Join a tournament by paying the entry fee in $TOURS\n\n"
            "/endtournament id winner - End a tournament (owner only) and award the prize pool to the winner’s wallet address (e.g., /endtournament 1 0x5fE8373C839948bFCB707A8a8A75A16E2634A725)\n\n"
            "/balance - Check your $MON and $TOURS balance\n"
            "/help - List all commands\n"
        )
        if receipt and receipt.status:
            action = "Action completed"
            if "createProfile" in pending["tx_data"]["data"]:
                action = "Profile created with 1 $TOURS funded to your wallet"
            elif "buyTours" in pending["tx_data"]["data"]:
                amount = int.from_bytes(bytes.fromhex(pending["tx_data"]["data"][10:]), byteorder='big') / 10**18
                action = f"Successfully purchased {amount} $TOURS"
            elif "transfer" in pending["tx_data"]["data"]:
                action = "Successfully sent $TOURS to the recipient"
            elif "createClimbingLocation" in pending["tx_data"]["data"]:
                action = f"Climb '{pending.get('name', 'Unknown')}' ({pending.get('difficulty', 'Unknown')}) created"
            await update.message.reply_text(f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 {action}.", parse_mode="Markdown")
            if CHAT_HANDLE and TELEGRAM_TOKEN:
                message = f"New activity by {escape_html(update.effective_user.username or update.effective_user.first_name)} on EmpowerTours! 🧗 <a href=\"{EXPLORER_URL}/tx/{tx_hash}\">Tx: {escape_html(tx_hash)}</a>"
                await send_notification(CHAT_HANDLE, message)
            if pending.get("next_tx"):
                next_tx_data = pending["next_tx"]
                if next_tx_data["type"] == "create_climbing_location":
                    nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                    tx = await contract.functions.createClimbingLocation(
                        next_tx_data["name"],
                        next_tx_data["difficulty"],
                        next_tx_data["latitude"],
                        next_tx_data["longitude"],
                        next_tx_data["photo_hash"]
                    ).build_transaction({
                        'chainId': 10143,
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
                        f"Approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for climb '{next_tx_data['name']}' ({next_tx_data['difficulty']}) using 10 $TOURS."
                    )
                    logger.info(f"/handle_tx_hash processed approval, next transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
                    return
                elif next_tx_data["type"] == "add_journal_entry":
                    nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                    tx = await contract.functions.addJournalEntryWithDetails(
                        next_tx_data["content_hash"],
                        next_tx_data["location"],
                        next_tx_data["difficulty"],
                        next_tx_data["is_shared"],
                        next_tx_data["cast_hash"]
                    ).build_transaction({
                        'chainId': 10143,
                        'from': pending["wallet_address"],
                        'nonce': nonce,
                        'gas': 500000,
                        'gas_price': await w3.eth.gas_price
                    })
                    await set_pending_wallet(user_id, {
                        "awaiting_tx": True,
                        "tx_data": tx,
                        "wallet_address": pending["wallet_address"],
                        "timestamp": time.time()
                    })
                    await update.message.reply_text(
                        f"Approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for journal entry using 5 $TOURS."
                    )
                    logger.info(f"/handle_tx_hash processed approval, next transaction built for journal, took {time.time() - start_time:.2f} seconds")
                    return
            await delete_pending_wallet(user_id)
            logger.info(f"/handle_tx_hash confirmed for user {user_id}, took {time.time() - start_time:.2f} seconds")
        else:
            await update.message.reply_text("Transaction failed or pending. Check and try again! 😅")
            logger.info(f"/handle_tx_hash failed or pending, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in handle_tx_hash: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received command: {update.message.text} from user {update.effective_user.id} in chat {update.effective_chat.id}")
    try:
        await update.message.reply_text(f"Debug: Received command '{update.message.text}'. Please use a valid command like /start or /tutorial.")
        logger.info(f"Sent /debug_command response to user {update.effective_user.id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in debug_command: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

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
        logger.info(f"Generated connect URL: {connect_url}")
        keyboard = [[InlineKeyboardButton("Connect with MetaMask/WalletConnect", url=connect_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = (
            "Click the button to connect your wallet via MetaMask or WalletConnect. "
            "On mobile, copy this link and open it in the MetaMask app's browser (Menu > Browser). "
            "If you see a chain ID mismatch, go to MetaMask Settings > Networks, remove all Monad Testnet entries, and reconnect. "
            "After connecting, use /createprofile to create your profile or /balance to check your status. "
            "If the link fails, contact support at [EmpowerTours Chat](https://t.me/empowertourschat)."
        )
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")
        logger.info(f"Sent /connectwallet response to user {update.effective_user.id}: {message}, took {time.time() - start_time:.2f} seconds")
        await set_pending_wallet(user_id, {"awaiting_wallet": True, "timestamp": time.time()})
        logger.info(f"Added user {user_id} to pending_wallets: {pending_wallets.get(user_id)}")
    except Exception as e:
        logger.error(f"Error in /connectwallet for user {user_id}: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

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
            await context.bot.send_message(user_id, f"Wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address}) connected! Try /createprofile. 🪙", parse_mode="Markdown")
            await delete_pending_wallet(user_id)
            logger.info(f"Wallet connected for user {user_id}: {checksum_address}, took {time.time() - start_time:.2f} seconds")
        else:
            await context.bot.send_message(user_id, "Invalid wallet address or blockchain unavailable. Try /connectwallet again.")
            logger.info(f"/handle_wallet_address failed due to invalid address or blockchain, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in handle_wallet_address: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await context.bot.send_message(user_id, f"Error: {str(e)}. Try again! 😅")

async def buy_tours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /buyTours command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /buyTours command disabled")
        await update.message.reply_text("Buying $TOURS unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/buyTours failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract or not tours_contract:
        logger.error("Web3 or contract not initialized, /buyTours command disabled")
        await update.message.reply_text("Buying $TOURS unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/buyTours failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Use: /buyTours [amount] 🪙 (e.g., /buyTours 10 to buy 10 $TOURS)")
            logger.info(f"/buyTours failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        try:
            amount = int(float(args[0]) * 10**18)  # Convert to Wei (1 $TOURS = 10^18 Wei)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            await update.message.reply_text("Invalid amount. Use a positive number (e.g., /buyTours 10 for 10 $TOURS). 😅")
            logger.info(f"/buyTours failed due to invalid amount, took {time.time() - start_time:.2f} seconds")
            return
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("No wallet connected. Use /connectwallet first! 🪙")
            logger.info(f"/buyTours failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        logger.info(f"Wallet address for user {user_id}: {wallet_address}")

        # Verify Web3 connection
        is_connected = await w3.is_connected()
        if not is_connected:
            logger.error("Web3 not connected to Monad testnet")
            await update.message.reply_text("Blockchain connection failed. Try again later or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/buyTours failed due to Web3 connection, took {time.time() - start_time:.2f} seconds")
            return

        # Ensure checksum address
        try:
            checksum_address = w3.to_checksum_address(wallet_address)
            logger.info(f"Using contract address: {contract.address}")
        except Exception as e:
            logger.error(f"Error converting wallet address to checksum: {str(e)}")
            await update.message.reply_text(f"Invalid wallet address format: {str(e)}. Try /connectwallet again. 😅")
            logger.info(f"/buyTours failed due to checksum error, took {time.time() - start_time:.2f} seconds")
            return

        # Check profile existence with $TOURS balance first
        profile_exists = False
        try:
            tours_balance = await tours_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
            logger.info(f"$TOURS balance for {checksum_address}: {tours_balance / 10**18} $TOURS")
            if tours_balance > 0:
                profile_exists = True
                logger.info(f"Profile assumed to exist due to non-zero $TOURS balance: {tours_balance / 10**18}")
        except Exception as e:
            logger.error(f"Error checking $TOURS balance: {str(e)}")

        # Fallback: Check profile with reduced retries
        if not profile_exists:
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    profile = await contract.functions.profiles(checksum_address).call({'gas': 500000})
                    logger.info(f"Profile check attempt {attempt}/{max_retries} for {checksum_address}: {profile}")
                    if profile[0]:
                        profile_exists = True
                        break
                except Exception as e:
                    logger.error(f"Error checking profile existence (attempt {attempt}/{max_retries}): {str(e)}")
                    if attempt == max_retries:
                        logger.warning(f"Profile check failed after {max_retries} attempts")
                    await asyncio.sleep(3)

        # Check ProfileCreated events
        if not profile_exists:
            try:
                profile_created_event = contract.events.ProfileCreated.create_filter(
                    fromBlock=0,
                    argument_filters={'user': checksum_address}
                )
                events = await profile_created_event.get_all_entries()
                if events:
                    profile_exists = True
                    logger.info(f"Profile confirmed via ProfileCreated event for {checksum_address}: {len(events)} events found")
            except Exception as e:
                logger.error(f"Error checking ProfileCreated events: {str(e)}")

        if not profile_exists:
            await update.message.reply_text(
                f"No profile exists for wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})! Use /createprofile to create a profile before buying $TOURS. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                parse_mode="Markdown"
            )
            logger.info(f"/buyTours failed: no profile for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
            return

        # Get TOURS_PRICE and check $MON balance
        try:
            tours_price = await contract.functions.TOURS_PRICE().call({'gas': 500000})
            logger.info(f"TOURS_PRICE retrieved: {tours_price} wei per $TOURS")
            mon_required = (amount * tours_price) // 10**18
            mon_balance = await w3.eth.get_balance(checksum_address)
            logger.info(f"$MON balance for {checksum_address}: {mon_balance / 10**18} $MON")
            if mon_balance < mon_required + (300000 * await w3.eth.gas_price):
                await update.message.reply_text(
                    f"Insufficient $MON balance. You have {mon_balance / 10**18} $MON, need {mon_required / 10**18} $MON plus gas (~0.015 $MON). Top up at https://testnet.monad.xyz/faucet. 😅"
                )
                logger.info(f"/buyTours failed due to insufficient $MON, took {time.time() - start_time:.2f} seconds")
                return
            # Check contract $TOURS balance
            contract_tours_balance = await tours_contract.functions.balanceOf(contract.address).call({'gas': 500000})
            logger.info(f"Contract $TOURS balance: {contract_tours_balance / 10**18} $TOURS")
            if contract_tours_balance < amount:
                await update.message.reply_text(
                    f"Contract lacks sufficient $TOURS to fulfill your request. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                    parse_mode="Markdown"
                )
                logger.info(f"/buyTours failed due to insufficient contract $TOURS, took {time.time() - start_time:.2f} seconds")
                return
        except Exception as e:
            logger.error(f"Error calling TOURS_PRICE or checking balance: {str(e)}")
            await update.message.reply_text(f"Failed to retrieve $TOURS price or balance: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/buyTours failed due to TOURS_PRICE/balance error, took {time.time() - start_time:.2f} seconds")
            return

        # Simulate buyTours to confirm
        try:
            await contract.functions.buyTours(amount).call({
                'from': checksum_address,
                'value': mon_required,
                'gas': 500000
            })
        except Exception as e:
            revert_reason = str(e)
            logger.error(f"buyTours simulation failed: {revert_reason}")
            if "ProfileRequired" in revert_reason:
                await update.message.reply_text(
                    f"No profile exists for wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})! Use /createprofile to create a profile before buying $TOURS. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                    parse_mode="Markdown"
                )
                logger.info(f"/buyTours failed: no profile for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
                return
            elif "InsufficientMonSent" in revert_reason:
                await update.message.reply_text(
                    f"Insufficient $MON for purchase. Need {mon_required / 10**18} $MON for {args[0]} $TOURS. Top up at https://testnet.monad.xyz/faucet. 😅"
                )
                logger.info(f"/buyTours failed due to insufficient $MON, took {time.time() - start_time:.2f} seconds")
                return
            else:
                await update.message.reply_text(
                    f"Transaction simulation failed: {revert_reason}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                    parse_mode="Markdown"
                )
                logger.info(f"/buyTours failed due to simulation error, took {time.time() - start_time:.2f} seconds")
                return

        # Build transaction
        try:
            nonce = await w3.eth.get_transaction_count(checksum_address)
            tx = await contract.functions.buyTours(amount).build_transaction({
                'from': checksum_address,
                'value': mon_required,
                'nonce': nonce,
                'gas': 300000,
                'gas_price': await w3.eth.gas_price
            })
            logger.info(f"Transaction built for user {user_id}: {json.dumps(tx, default=str)}")
            await set_pending_wallet(user_id, {
                "awaiting_tx": True,
                "tx_data": tx,
                "wallet_address": checksum_address,
                "timestamp": time.time()
            })
            await update.message.reply_text(
                f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction to buy {args[0]} $TOURS using {w3.from_wei(mon_required, 'ether')} $MON with your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})).",
                parse_mode="Markdown"
            )
            logger.info(f"/buyTours transaction built, awaiting signing for user {user_id}, took {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error building transaction for user {user_id}: {str(e)}")
            await update.message.reply_text(f"Failed to build transaction: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/buyTours failed due to transaction build error, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /buyTours for user {user_id}: {str(e)}")
        await update.message.reply_text(f"Unexpected error: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        logger.info(f"/buyTours failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def send_tours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /sendTours command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /sendTours command disabled")
        await update.message.reply_text("Sending $TOURS unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/sendTours failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not tours_contract:
        logger.error("Web3 or tours_contract not initialized, /sendTours command disabled")
        await update.message.reply_text("Sending $TOURS unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/sendTours failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Use: /sendTours [recipient] [amount] 🪙 (e.g., /sendTours 0x123...456 10 to send 10 $TOURS)")
            logger.info(f"/sendTours failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        recipient = args[0]
        try:
            amount = int(float(args[1]) * 10**18)  # Convert to Wei (1 $TOURS = 10^18 Wei)
        except ValueError:
            await update.message.reply_text("Invalid amount. Use a number (e.g., /sendTours 0x123...456 10 for 10 $TOURS). 😅")
            logger.info(f"/sendTours failed due to invalid amount, took {time.time() - start_time:.2f} seconds")
            return
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("No wallet connected. Use /connectwallet first! 🪙")
            logger.info(f"/sendTours failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        logger.info(f"Wallet address for user {user_id}: {wallet_address}")

        # Verify Web3 connection
        is_connected = await w3.is_connected()
        if not is_connected:
            logger.error("Web3 not connected to Monad testnet")
            await update.message.reply_text("Blockchain connection failed. Try again later or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/sendTours failed due to Web3 connection, took {time.time() - start_time:.2f} seconds")
            return

        # Ensure checksum addresses
        try:
            checksum_address = w3.to_checksum_address(wallet_address)
            recipient_checksum_address = w3.to_checksum_address(recipient)
        except Exception as e:
            logger.error(f"Error converting addresses to checksum: {str(e)}")
            await update.message.reply_text(f"Invalid wallet or recipient address format: {str(e)}. Check the address and try again. 😅")
            logger.info(f"/sendTours failed due to checksum error, took {time.time() - start_time:.2f} seconds")
            return

        # Check sender's $TOURS balance
        try:
            balance = await tours_contract.functions.balanceOf(checksum_address).call()
            logger.info(f"$TOURS balance for {checksum_address}: {balance / 10**18} $TOURS")
            if balance < amount:
                await update.message.reply_text(f"Insufficient $TOURS balance. You have {balance / 10**18} $TOURS, need {amount / 10**18} $TOURS. Use /buyTours or /balance. 😅")
                logger.info(f"/sendTours failed due to insufficient balance, took {time.time() - start_time:.2f} seconds")
                return
        except Exception as e:
            logger.error(f"Error checking $TOURS balance: {str(e)}")
            await update.message.reply_text(f"Failed to check $TOURS balance: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/sendTours failed due to balance check error, took {time.time() - start_time:.2f} seconds")
            return

        # Build transaction
        try:
            nonce = await w3.eth.get_transaction_count(checksum_address)
            tx = await tours_contract.functions.transfer(recipient_checksum_address, amount).build_transaction({
                'from': checksum_address,
                'nonce': nonce,
                'gas': 100000,
                'gas_price': await w3.eth.gas_price
            })
            logger.info(f"Transaction built for user {user_id}: {json.dumps(tx, default=str)}")
            await set_pending_wallet(user_id, {
                "awaiting_tx": True,
                "tx_data": tx,
                "wallet_address": checksum_address,
                "timestamp": time.time()
            })
            await update.message.reply_text(
                f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction to send {args[1]} $TOURS to [{recipient_checksum_address[:6]}...]({EXPLORER_URL}/address/{recipient_checksum_address}) using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})).",
                parse_mode="Markdown"
            )
            logger.info(f"/sendTours transaction built, awaiting signing for user {user_id}, took {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error building transaction for user {user_id}: {str(e)}")
            await update.message.reply_text(f"Failed to build transaction: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/sendTours failed due to transaction build error, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /sendTours for user {user_id}: {str(e)}")
        await update.message.reply_text(f"Unexpected error: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        logger.info(f"/sendTours failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def create_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /createprofile command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /createprofile command disabled")
        await update.message.reply_text("Profile creation unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/createprofile failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract or not tours_contract:
        logger.error("Web3 or contract not initialized, /createprofile command disabled")
        await update.message.reply_text("Profile creation unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/createprofile failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            logger.warning(f"No wallet found for user {user_id}")
            await update.message.reply_text("No wallet connected. Use /connectwallet first! 🪙")
            logger.info(f"/createprofile failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        logger.info(f"Wallet address for user {user_id}: {wallet_address}")
        
        # Verify Web3 connection
        is_connected = await w3.is_connected()
        if not is_connected:
            logger.error("Web3 not connected to Monad testnet")
            await update.message.reply_text("Blockchain connection failed. Try again later or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/createprofile failed due to Web3 connection, took {time.time() - start_time:.2f} seconds")
            return

        # Ensure checksum address
        try:
            checksum_address = w3.to_checksum_address(wallet_address)
            logger.info(f"Using contract address: {contract.address}")
        except Exception as e:
            logger.error(f"Error converting wallet address to checksum: {str(e)}")
            await update.message.reply_text(f"Invalid wallet address format: {str(e)}. Try /connectwallet again. 😅")
            logger.info(f"/createprofile failed due to checksum error, took {time.time() - start_time:.2f} seconds")
            return

        # Check $TOURS balance as primary indicator
        profile_exists = False
        try:
            tours_balance = await tours_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
            logger.info(f"$TOURS balance for {checksum_address}: {tours_balance / 10**18} $TOURS")
            if tours_balance > 0:
                profile_exists = True
                logger.info(f"Profile assumed to exist due to non-zero $TOURS balance: {tours_balance / 10**18}")
                await update.message.reply_text(
                    f"A profile already exists for wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})! Use /balance to check your status or try commands like /journal, /buildaclimb, /buyTours, or /createtournament. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat) if needed. 😅",
                    parse_mode="Markdown"
                )
                logger.info(f"/createprofile failed: profile exists for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
                return
        except Exception as e:
            logger.error(f"Error checking $TOURS balance: {str(e)}")

        # Fallback: Check profile with reduced retries
        if not profile_exists:
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    profile = await contract.functions.profiles(checksum_address).call({'gas': 500000})
                    logger.info(f"Profile check attempt {attempt}/{max_retries} for {checksum_address}: {profile}")
                    if profile[0]:
                        profile_exists = True
                        await update.message.reply_text(
                            f"A profile already exists for wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})! Use /balance to check your status or try commands like /journal, /buildaclimb, /buyTours, or /createtournament. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat) if needed. 😅",
                            parse_mode="Markdown"
                        )
                        logger.info(f"/createprofile failed: profile exists for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
                        return
                    break
                except Exception as e:
                    logger.error(f"Error checking profile existence (attempt {attempt}/{max_retries}): {str(e)}")
                    if attempt == max_retries:
                        logger.warning(f"Profile check failed after {max_retries} attempts")
                    await asyncio.sleep(3)

        # Check ProfileCreated events
        if not profile_exists:
            try:
                profile_created_event = contract.events.ProfileCreated.create_filter(
                    fromBlock=0,
                    argument_filters={'user': checksum_address}
                )
                events = await profile_created_event.get_all_entries()
                if events:
                    profile_exists = True
                    logger.info(f"Profile confirmed via ProfileCreated event for {checksum_address}: {len(events)} events found")
                    await update.message.reply_text(
                        f"A profile already exists for wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})! Use /balance to check your status or try commands like /journal or /buildaclimb. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat) if needed. 😅",
                        parse_mode="Markdown"
                    )
                    logger.info(f"/createprofile failed: profile exists for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
                    return
            except Exception as e:
                logger.error(f"Error checking ProfileCreated events: {str(e)}")

        # Simulate createProfile as final check
        if not profile_exists:
            try:
                await contract.functions.createProfile().call({
                    'from': checksum_address,
                    'value': w3.to_wei(1, 'ether'),
                    'gas': 500000
                })
            except Exception as e:
                revert_reason = str(e)
                logger.error(f"createProfile simulation failed: {revert_reason}")
                if "ProfileExists" in revert_reason:
                    profile_exists = True
                    await update.message.reply_text(
                        f"A profile already exists for wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})! Use /balance to check your status or try commands like /journal or /buildaclimb. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat) if needed. 😅",
                        parse_mode="Markdown"
                    )
                    logger.info(f"/createprofile failed: profile exists for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
                    return

        # Get profile fee (1 $MON)
        try:
            profile_fee = await contract.functions.profileFee().call({'gas': 500000})
            logger.info(f"Profile fee retrieved: {profile_fee} wei")
            expected_fee = w3.to_wei(1, 'ether')
            if profile_fee != expected_fee:
                logger.warning(f"Profile fee is {profile_fee} wei, expected {expected_fee} wei")
        except Exception as e:
            logger.error(f"Error calling profileFee(): {str(e)}")
            await update.message.reply_text(f"Failed to retrieve profile fee: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/createprofile failed due to profileFee error, took {time.time() - start_time:.2f} seconds")
            return

        # Check $MON balance
        try:
            mon_balance = await w3.eth.get_balance(checksum_address)
            logger.info(f"$MON balance for {checksum_address}: {mon_balance / 10**18} $MON")
            if mon_balance < profile_fee + (300000 * await w3.eth.gas_price):
                await update.message.reply_text(
                    f"Insufficient $MON balance. You have {mon_balance / 10**18} $MON, need {profile_fee / 10**18} $MON plus gas (~0.015 $MON). Top up at https://testnet.monad.xyz/faucet. 😅"
                )
                logger.info(f"/createprofile failed due to insufficient $MON, took {time.time() - start_time:.2f} seconds")
                return
        except Exception as e:
            logger.error(f"Error checking $MON balance: {str(e)}")
            await update.message.reply_text(f"Failed to check $MON balance: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/createprofile failed due to balance check error, took {time.time() - start_time:.2f} seconds")
            return

        # Build transaction
        try:
            nonce = await w3.eth.get_transaction_count(checksum_address)
            tx = await contract.functions.createProfile().build_transaction({
                'from': checksum_address,
                'value': profile_fee,
                'nonce': nonce,
                'gas': 300000,
                'gas_price': await w3.eth.gas_price
            })
            logger.info(f"Transaction built for user {user_id}: {json.dumps(tx, default=str)}")
            await set_pending_wallet(user_id, {
                "awaiting_tx": True,
                "tx_data": tx,
                "wallet_address": checksum_address,
                "timestamp": time.time()
            })
            await update.message.reply_text(
                f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} in your browser to sign the transaction for profile creation (1 $MON). You will receive 1 $TOURS upon confirmation. After signing."
            )
            logger.info(f"/createprofile transaction built, awaiting signing for user {user_id}, took {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error building transaction for user {user_id}: {str(e)}")
            await update.message.reply_text(f"Failed to build transaction: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/createprofile failed due to transaction build error, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /createprofile for user {user_id}: {str(e)}")
        await update.message.reply_text(f"Unexpected error: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        logger.info(f"/createprofile failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def journal_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /journal command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /journal command disabled")
        await update.message.reply_text("Journal entry unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/journal failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract:
        logger.error("Web3 not initialized, /journal command disabled")
        await update.message.reply_text("Journal entry unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/journal failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        content = " ".join(context.args)
        if not content:
            await update.message.reply_text("Use: /journal [your journal entry] Then photo. 📸")
            logger.info(f"/journal failed due to missing content, took {time.time() - start_time:.2f} seconds")
            return
        await update.message.reply_text(f"Great, {update.effective_user.first_name}! Send photo. 🌟")
        await set_journal_data(user_id, {"content": content, "awaiting_photo": True, "timestamp": time.time()})
        logger.info(f"/journal initiated for user {user_id}, awaiting photo, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /journal: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received photo from user {user_id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, photo handling disabled")
        await update.message.reply_text("Photo processing unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/handle_photo failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract:
        logger.error("Web3 not initialized, photo handling disabled")
        await update.message.reply_text("Photo processing unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/handle_photo failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        # Hash the file_id to fixed 32-byte hex (reduces gas/storage) for both journal and climb
        photo_hash = w3.keccak(text=file_id).hex()  # Now ~66 chars fixed
        journal = await get_journal_data(user_id)
        entry_type = 'journal' if journal and journal.get("awaiting_photo") else 'climb'
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO media_files (hash, file_id, user_id, entry_type, entry_id) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (hash) DO NOTHING",
                photo_hash, file_id, user_id, entry_type, None
            )
        if journal and journal.get("awaiting_photo"):
            journal["photo_hash"] = photo_hash
            journal["awaiting_location"] = True
            del journal["awaiting_photo"]
            await set_journal_data(user_id, journal)
            await update.message.reply_text("Photo received (hashed for efficiency)! Now send the location using the paperclip icon > Location.")
            logger.info(f"/handle_photo processed for journal, awaiting location for user {user_id}, took {time.time() - start_time:.2f} seconds")
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
        await update.message.reply_text(f"Error processing photo: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        logger.info(f"/handle_photo failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def add_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /comment command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /comment command disabled")
        await update.message.reply_text("Commenting unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/comment failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract:
        logger.error("Web3 not initialized, /comment command disabled")
        await update.message.reply_text("Commenting unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/comment failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Use: /comment [id] [your comment] (0.1 $MON) 🗣️")
            logger.info(f"/comment failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        entry_id = int(args[0])
        content = " ".join(args[1:])
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            logger.info(f"/comment failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        checksum_address = w3.to_checksum_address(wallet_address)
        comment_fee = await contract.functions.commentFee().call()
        nonce = await w3.eth.get_transaction_count(checksum_address)
        tx = await contract.functions.addComment(entry_id, content).build_transaction({
            'from': checksum_address,
            'value': comment_fee,
            'nonce': nonce,
            'gas': 200000,
            'gas_price': await w3.eth.gas_price
        })
        await update.message.reply_text(
            f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for comment (0.1 $MON) using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})).",
            parse_mode="Markdown"
        )
        await set_pending_wallet(user_id, {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": checksum_address,
            "timestamp": time.time()
        })
        logger.info(f"/comment transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /comment: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def journals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /journals command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not w3 or not contract:
        await update.message.reply_text("Blockchain connection unavailable. Try again later! 😅")
        logger.info(f"/journals failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        global journal_cache, cache_timestamp
        current_time = time.time()
        if journal_cache and current_time - cache_timestamp < CACHE_TTL:
            entry_list = journal_cache
        else:
            entry_count = await contract.functions.getJournalEntryCount().call({'gas': 500000})
            logger.info(f"Journal entry count: {entry_count}")
            if entry_count == 0:
                await update.message.reply_text("No journal entries found. Create one with /journal! 📝")
                logger.info(f"/journals found no entries, took {time.time() - start_time:.2f} seconds")
                return
            coros = [contract.functions.getJournalEntry(i).call({'gas': 500000}) for i in range(entry_count)]
            entries = await asyncio.gather(*coros, return_exceptions=True)
            entry_list = []
            for i, entry in enumerate(entries):
                if isinstance(entry, Exception):
                    logger.error(f"Error retrieving journal {i}: {str(entry)}")
                    continue
                content = entry[1]
                has_photo = False
                if ' (photo: ' in content:
                    has_photo = True
                    content = content.rsplit(' (photo: ', 1)[0]
                entry_list.append(
                    f"📝 Entry #{i} by [{entry[0][:6]}...]({EXPLORER_URL}/address/{entry[0]})\n"
                    f"   Content: {content}{' (has photo)' if has_photo else ''}\n"
                    f"   Location: {entry[5]}\n"
                    f"   Difficulty: {entry[6]}\n"
                    f"   Created: {datetime.fromtimestamp(entry[2]).strftime('%Y-%m-%d %H:%M:%S')}"
                )
            journal_cache = entry_list
            cache_timestamp = current_time
        if not entry_list:
            await update.message.reply_text("No journal entries found. Create one with /journal! 📝")
        else:
            await update.message.reply_text("\n\n".join(entry_list), parse_mode="Markdown")
        logger.info(f"/journals retrieved {len(entry_list)} entries, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /journals: {str(e)}")
        await update.message.reply_text(f"Error retrieving journals: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        logger.info(f"/journals failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def viewjournal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /viewjournal command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not w3 or not contract:
        await update.message.reply_text("Blockchain connection unavailable. Try again later! 😅")
        logger.info(f"/viewjournal failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Use: /viewjournal [id] 📝")
            logger.info(f"/viewjournal failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        entry_id = int(args[0])
        entry = await contract.functions.getJournalEntry(entry_id).call({'gas': 500000})
        content = entry[1]
        photo_hash = None
        if ' (photo: ' in content:
            photo_hash = content.split(' (photo: ')[-1].rstrip(')')
            content = content.split(' (photo: ')[0]
        message = (
            f"📝 Journal Entry #{entry_id} by [{entry[0][:6]}...]({EXPLORER_URL}/address/{entry[0]})\n"
            f"Content: {content}\n"
            f"Location: {entry[5]}\n"
            f"Difficulty: {entry[6]}\n"
            f"Created: {datetime.fromtimestamp(entry[2]).strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        await update.message.reply_text(message, parse_mode="Markdown")
        if photo_hash:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT file_id FROM media_files WHERE hash = $1", photo_hash)
            if row:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=row['file_id'], caption="Photo for this journal entry")
            else:
                await update.message.reply_text("Photo not found in database.")
        comment_count = await contract.functions.getCommentCount(entry_id).call({'gas': 500000})
        coros = [contract.functions.journalComments(entry_id, j).call({'gas': 500000}) for j in range(comment_count)]
        comments_data = await asyncio.gather(*coros, return_exceptions=True)
        comments = []
        for j, comment in enumerate(comments_data):
            if isinstance(comment, Exception):
                logger.error(f"Error retrieving comment {j} for entry {entry_id}: {str(comment)}")
                continue
            comments.append(
                f"   - Comment by [{comment[0][:6]}...]: {comment[1]} ({datetime.fromtimestamp(comment[2]).strftime('%Y-%m-%d %H:%M:%S')})"
            )
        if comments:
            await update.message.reply_text(f"Comments ({comment_count}):\n" + "\n".join(comments), parse_mode="Markdown")
        logger.info(f"/viewjournal details for {entry_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /viewjournal: {str(e)}")
        await update.message.reply_text(f"Error retrieving entry: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        logger.info(f"/viewjournal failed due to error, took {time.time() - start_time:.2f} seconds")

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
        if has_photo:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT file_id FROM media_files WHERE hash = $1", photo_hash)
            if row:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=row['file_id'], caption="Photo for this climb")
            else:
                await update.message.reply_text("Photo not found in database.")
        logger.info(f"/viewclimb details for {loc_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /viewclimb: {str(e)}")
        await update.message.reply_text(f"Error retrieving climb: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
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
            logger.error("Web3 not connected to Monad testnet")
            await update.message.reply_text("Blockchain connection failed. Try again later or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/buildaclimb failed due to Web3 connection, took {time.time() - start_time:.2f} seconds")
            return

        # Ensure checksum address
        try:
            checksum_address = w3.to_checksum_address(wallet_address)
            logger.info(f"Using contract address: {contract.address}")
        except Exception as e:
            logger.error(f"Error converting wallet address to checksum: {str(e)}")
            await update.message.reply_text(f"Invalid wallet address format: {str(e)}. Try /connectwallet again. 😅")
            logger.info(f"/buildaclimb failed due to checksum error, took {time.time() - start_time:.2f} seconds")
            return

        # Check profile existence with $TOURS balance first
        profile_exists = False
        try:
            tours_balance = await tours_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
            logger.info(f"$TOURS balance for {checksum_address}: {tours_balance / 10**18} $TOURS")
            if tours_balance > 0:
                profile_exists = True
                logger.info(f"Profile assumed to exist due to non-zero $TOURS balance: {tours_balance / 10**18}")
        except Exception as e:
            logger.error(f"Error checking $TOURS balance: {str(e)}")

        # Fallback: Check profile with reduced retries
        if not profile_exists:
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    profile = await contract.functions.profiles(checksum_address).call({'gas': 500000})
                    logger.info(f"Profile check attempt {attempt}/{max_retries} for {checksum_address}: {profile}")
                    if profile[0]:
                        profile_exists = True
                        break
                except Exception as e:
                    logger.error(f"Error checking profile existence (attempt {attempt}/{max_retries}): {str(e)}")
                    if attempt == max_retries:
                        logger.warning(f"Profile check failed after {max_retries} attempts")
                    await asyncio.sleep(3)

        # Check ProfileCreated events
        if not profile_exists:
            try:
                profile_created_event = contract.events.ProfileCreated.create_filter(
                    fromBlock=0,
                    argument_filters={'user': checksum_address}
                )
                events = await profile_created_event.get_all_entries()
                if events:
                    profile_exists = True
                    logger.info(f"Profile confirmed via ProfileCreated event for {checksum_address}: {len(events)} events found")
            except Exception as e:
                logger.error(f"Error checking ProfileCreated events: {str(e)}")

        if not profile_exists:
            await update.message.reply_text(
                f"No profile exists for wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})! Use /createprofile to create a profile before building a climb. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                parse_mode="Markdown"
            )
            logger.info(f"/buildaclimb failed: no profile for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
            return

        # Check for duplicate climb name
        try:
            location_count = await contract.functions.getClimbingLocationCount().call({'gas': 500000})
            coros = [contract.functions.climbingLocations(i).call({'gas': 500000}) for i in range(location_count)]
            locations = await asyncio.gather(*coros, return_exceptions=True)
            for location in locations:
                if isinstance(location, Exception):
                    continue
                if location[1].lower() == name.lower():
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
        await update.message.reply_text(f"Unexpected error: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
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
    if not w3 or not contract or not tours_contract:
        logger.error("Web3 not initialized, location handling disabled")
        await update.message.reply_text("Location processing unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/handle_location failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        journal = await get_journal_data(user_id)
        if journal and journal.get("awaiting_location"):
            latitude = update.message.location.latitude
            longitude = update.message.location.longitude
            location_str = f"{latitude},{longitude}"
            content_hash = journal["content"]
            if "photo_hash" in journal:
                content_hash += f" (photo: {journal['photo_hash']})"
            difficulty = ''  # Empty as not provided
            is_shared = False
            cast_hash = ''
            session = await get_session(user_id)
            wallet_address = session.get("wallet_address") if session else None
            if not wallet_address:
                await update.message.reply_text("No wallet connected. Use /connectwallet first! 🪙")
                logger.info(f"/handle_location failed due to missing wallet for journal, took {time.time() - start_time:.2f} seconds")
                return
            checksum_address = w3.to_checksum_address(wallet_address)
            # Check profile existence
            profile_exists = False
            try:
                tours_balance = await tours_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
                if tours_balance > 0:
                    profile_exists = True
            except Exception as e:
                logger.error(f"Error checking profile for journal: {str(e)}")
            if not profile_exists:
                await update.message.reply_text(
                    f"No profile exists for wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})! Use /createprofile first. 😅",
                    parse_mode="Markdown"
                )
                logger.info(f"/handle_location failed: no profile for journal, took {time.time() - start_time:.2f} seconds")
                return
            # Check $TOURS balance and allowance
            try:
                journal_cost = await contract.functions.journalReward().call({'gas': 500000})
                tours_balance = await tours_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
                if tours_balance < journal_cost:
                    await update.message.reply_text(
                        f"Insufficient $TOURS. Need {journal_cost / 10**18} $TOURS, you have {tours_balance / 10**18}. Buy more with /buyTours! 😅"
                    )
                    logger.info(f"/handle_location failed: insufficient $TOURS for journal, took {time.time() - start_time:.2f} seconds")
                    return
                allowance = await tours_contract.functions.allowance(checksum_address, contract.address).call({'gas': 500000})
                if allowance < journal_cost:
                    nonce = await w3.eth.get_transaction_count(checksum_address)
                    approve_tx = await tours_contract.functions.approve(contract.address, journal_cost).build_transaction({
                        'chainId': 10143,
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
                            "type": "add_journal_entry",
                            "content_hash": content_hash,
                            "location": location_str,
                            "difficulty": difficulty,
                            "is_shared": is_shared,
                            "cast_hash": cast_hash
                        },
                        "entry_type": "journal",
                        "photo_hash": journal.get("photo_hash")
                    })
                    await update.message.reply_text(
                        f"Please open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to approve {journal_cost / 10**18} $TOURS for journal entry."
                    )
                    logger.info(f"/handle_location initiated approval for journal, took {time.time() - start_time:.2f} seconds")
                    return
            except Exception as e:
                logger.error(f"Error checking $TOURS for journal: {str(e)}")
                await update.message.reply_text(f"Failed to check $TOURS for journal: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
                logger.info(f"/handle_location failed due to $TOURS check for journal, took {time.time() - start_time:.2f} seconds")
                return

            # Build transaction for journal
            try:
                nonce = await w3.eth.get_transaction_count(checksum_address)
                tx = await contract.functions.addJournalEntryWithDetails(content_hash, location_str, difficulty, is_shared, cast_hash).build_transaction({
                    'chainId': 10143,
                    'from': checksum_address,
                    'nonce': nonce,
                    'gas': 500000,  # Increased gas limit
                    'gas_price': await w3.eth.gas_price
                })
                await set_pending_wallet(user_id, {
                    "awaiting_tx": True,
                    "tx_data": tx,
                    "wallet_address": checksum_address,
                    "timestamp": time.time(),
                    "entry_type": "journal",
                    "photo_hash": journal.get("photo_hash")
                })
                await update.message.reply_text(
                    f"Please open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for journal entry using 5 $TOURS."
                )
                await delete_journal_data(user_id)
                logger.info(f"/handle_location processed for journal, transaction built, took {time.time() - start_time:.2f} seconds")
                return
            except Exception as e:
                logger.error(f"Error building journal transaction: {str(e)}")
                await update.message.reply_text(f"Failed to build journal transaction: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
                logger.info(f"/handle_location failed due to journal tx build, took {time.time() - start_time:.2f} seconds")
                return
        elif 'pending_climb' in context.user_data:
            # Existing climb logic
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

            # Check $TOURS balance and allowance
            try:
                location_cost = await contract.functions.locationCreationCost().call({'gas': 500000})
                tours_balance = await tours_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
                logger.info(f"$TOURS balance for {checksum_address}: {tours_balance / 10**18} $TOURS")
                if tours_balance < location_cost:
                    await update.message.reply_text(
                        f"Insufficient $TOURS. Need {location_cost / 10**18} $TOURS, you have {tours_balance / 10**18}. Buy more with /buyTours! 😅"
                    )
                    logger.info(f"/handle_location failed: insufficient $TOURS for user {user_id}, took {time.time() - start_time:.2f} seconds")
                    return
                allowance = await tours_contract.functions.allowance(checksum_address, contract.address).call({'gas': 500000})
                logger.info(f"$TOURS allowance for {checksum_address}: {allowance / 10**18} $TOURS")
                if allowance < location_cost:
                    nonce = await w3.eth.get_transaction_count(checksum_address)
                    approve_tx = await tours_contract.functions.approve(contract.address, location_cost).build_transaction({
                        'chainId': 10143,
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
                            "photo_hash": photo_hash
                        },
                        "entry_type": "climb",
                        "photo_hash": photo_hash
                    })
                    await update.message.reply_text(
                        f"Please open https://version1-production.up.railway.app/public/connect.html?userId={user_id} in MetaMask’s browser to approve {location_cost / 10**18} $TOURS for climb creation."
                    )
                    logger.info(f"/handle_location initiated approval for user {user_id}, took {time.time() - start_time:.2f} seconds")
                    return
            except Exception as e:
                logger.error(f"Error checking $TOURS balance or allowance: {str(e)}")
                await update.message.reply_text(f"Failed to check $TOURS balance or allowance: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
                logger.info(f"/handle_location failed due to balance/allowance error, took {time.time() - start_time:.2f} seconds")
                return

            # Simulate createClimbingLocation
            try:
                await contract.functions.createClimbingLocation(name, difficulty, latitude, longitude, photo_hash).call({
                    'from': checksum_address,
                    'gas': 500000
                })
            except Exception as e:
                revert_reason = str(e)
                logger.error(f"createClimbingLocation simulation failed: {revert_reason}")
                await update.message.reply_text(
                    f"Transaction simulation failed: {revert_reason}. Check parameters (name, difficulty, coordinates) or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                    parse_mode="Markdown"
                )
                logger.info(f"/handle_location failed due to simulation error, took {time.time() - start_time:.2f} seconds")
                return

            # Build transaction with increased gas
            try:
                nonce = await w3.eth.get_transaction_count(checksum_address)
                tx = await contract.functions.createClimbingLocation(name, difficulty, latitude, longitude, photo_hash).build_transaction({
                    'chainId': 10143,
                    'from': checksum_address,
                    'nonce': nonce,
                    'gas': 500000,  # Increased gas limit
                    'gas_price': await w3.eth.gas_price
                })
                logger.info(f"Transaction built for user {user_id}: {json.dumps(tx, default=str)}")
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
                    "entry_type": "climb",
                    "photo_hash": photo_hash
                })
                await update.message.reply_text(
                    f"Please open https://version1-production.up.railway.app/public/connect.html?userId={user_id} in MetaMask’s browser to sign the transaction for climb '{name}' ({difficulty}) using 10 $TOURS."
                )
                logger.info(f"/handle_location processed, transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
            except Exception as e:
                logger.error(f"Error building transaction for user {user_id}: {str(e)}")
                await update.message.reply_text(f"Failed to build transaction: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
                logger.info(f"/handle_location failed due to transaction build error, took {time.time() - start_time:.2f} seconds")
        else:
            await update.message.reply_text("No climb or journal creation in progress. Start with /buildaclimb or /journal. 😅")
            logger.info(f"/handle_location failed: no pending climb or journal for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /handle_location for user {user_id}: {str(e)}")
        await update.message.reply_text(f"Unexpected error: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
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
    if not w3 or not contract or not tours_contract:
        logger.error("Web3 not initialized, /purchaseclimb command disabled")
        await update.message.reply_text("Climb purchase unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/purchaseclimb failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
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
        # Get cost (assume locationCreationCost is the purchase cost too)
        purchase_cost = await contract.functions.locationCreationCost().call({'gas': 500000})
        # Check $TOURS balance
        tours_balance = await tours_contract.functions.balanceOf(checksum_address).call({'gas': 500000})
        if tours_balance < purchase_cost:
            await update.message.reply_text(
                f"Insufficient $TOURS. Need {purchase_cost / 10**18} $TOURS, you have {tours_balance / 10**18}. Buy more with /buyTours! 😅"
            )
            logger.info(f"/purchaseclimb failed: insufficient $TOURS for user {user_id}, took {time.time() - start_time:.2f} seconds")
            return
        # Check allowance
        allowance = await tours_contract.functions.allowance(checksum_address, contract.address).call({'gas': 500000})
        if allowance < purchase_cost:
            nonce = await w3.eth.get_transaction_count(checksum_address)
            approve_tx = await tours_contract.functions.approve(contract.address, purchase_cost).build_transaction({
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
                f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to approve {purchase_cost / 10**18} $TOURS for climb purchase using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})). After approval, you'll sign the purchase transaction.",
                parse_mode="Markdown"
            )
            logger.info(f"/purchaseclimb initiated approval for user {user_id}, took {time.time() - start_time:.2f} seconds")
            return
        # If allowance OK, build purchase tx
        nonce = await w3.eth.get_transaction_count(checksum_address)
        tx = await contract.functions.purchaseClimbingLocation(location_id).build_transaction({
            'from': checksum_address,
            'nonce': nonce,
            'gas': 200000,
            'gas_price': await w3.eth.gas_price,
            'value': 0
        })
        await update.message.reply_text(
            f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for climb purchase (10 $TOURS) using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})).",
            parse_mode="Markdown"
        )
        await set_pending_wallet(user_id, {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": checksum_address,
            "timestamp": time.time()
        })
        logger.info(f"/purchaseclimb transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /purchaseclimb: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

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
            location_count = await contract.functions.getClimbingLocationCount().call({'gas': 500000})
            logger.info(f"Climbing location count: {location_count}")
            if location_count == 0:
                try:
                    events = await contract.events.ClimbingLocationCreated.create_filter(
                        fromBlock=0,
                        argument_filters={'creator': None}
                    ).get_all_entries()
                    logger.info(f"Found {len(events)} ClimbingLocationCreated events")
                    if events:
                        await update.message.reply_text(
                            f"No climbs found in mapping, but {len(events)} climbs detected via events. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat) to resolve storage issue. 😅",
                            parse_mode="Markdown"
                        )
                        logger.info(f"/findaclimb found events but no climbs in mapping, took {time.time() - start_time:.2f} seconds")
                        return
                except Exception as e:
                    logger.error(f"Error checking ClimbingLocationCreated events: {str(e)}")
                await update.message.reply_text("No climbs found. Create one with /buildaclimb! 🪨")
                logger.info(f"/findaclimb found no climbs, took {time.time() - start_time:.2f} seconds")
                return
            coros = [contract.functions.climbingLocations(i).call({'gas': 500000}) for i in range(location_count)]
            locations = await asyncio.gather(*coros, return_exceptions=True)
            tour_list = []
            for i, location in enumerate(locations):
                if isinstance(location, Exception):
                    logger.error(f"Error retrieving climb {i}: {str(location)}")
                    continue
                photo_info = " (has photo)" if location[5] else ""
                tour_list.append(
                    f"🧗 Climb ID: {i} - {location[1]}{photo_info} ({location[2]}) by [{location[0][:6]}...]({EXPLORER_URL}/address/{location[0]})\n"
                    f"   Location: {location[3]/1000000:.6f},{location[4]/1000000:.6f}\n"
                    f"   Map: https://www.google.com/maps?q={location[3]/1000000:.6f},{location[4]/1000000:.6f}\n"
                    f"   Created: {datetime.fromtimestamp(location[6]).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"   Purchases: {location[10]}"
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
        await update.message.reply_text(f"Error retrieving climbs: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        logger.info(f"/findaclimb failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

async def createtournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /createtournament command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /createtournament command disabled")
        await update.message.reply_text("Tournament creation unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/createtournament failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract:
        logger.error("Web3 not initialized, /createtournament command disabled")
        await update.message.reply_text("Tournament creation unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/createtournament failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Use: /createtournament [fee] 🏆")
            logger.info(f"/createtournament failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        entry_fee = int(float(args[0]) * 10**18)
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            logger.info(f"/createtournament failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        checksum_address = w3.to_checksum_address(wallet_address)
        nonce = await w3.eth.get_transaction_count(checksum_address)
        tx = await contract.functions.createTournament(entry_fee).build_transaction({
            'from': checksum_address,
            'nonce': nonce,
            'gas': 200000,
            'gas_price': await w3.eth.gas_price,
            'value': 0
        })
        await update.message.reply_text(
            f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for tournament creation ({entry_fee / 10**18} $TOURS) using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})).",
            parse_mode="Markdown"
        )
        await set_pending_wallet(user_id, {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": checksum_address,
            "timestamp": time.time()
        })
        logger.info(f"/createtournament transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /createtournament: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def tournaments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /tournaments command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not w3 or not contract:
        await update.message.reply_text("Blockchain unavailable. Try again later! 😅")
        logger.info(f"/tournaments failed due to blockchain issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        count = await contract.functions.getTournamentCount().call()
        if count == 0:
            await update.message.reply_text("No tournaments created yet. Start one with /createtournament fee! 🏆")
            logger.info(f"/tournaments: No tournaments found, took {time.time() - start_time:.2f} seconds")
            return
        coros = [contract.functions.tournaments(i).call() for i in range(count)]
        tournaments_data = await asyncio.gather(*coros, return_exceptions=True)
        msg = "**Tournaments List:**\n"
        for i, t in enumerate(tournaments_data):
            if isinstance(t, Exception):
                logger.error(f"Error retrieving tournament {i}: {str(t)}")
                continue
            entry_fee = t[0] / 10**18
            pot = t[1] / 10**18
            winner = t[2]
            active = t[3]
            name = t[7] if len(t) > 7 else "Unnamed"
            participants = pot / entry_fee if entry_fee > 0 else 0
            status = "Active" if active else f"Ended (Winner: {winner[:6]}...{winner[-4:]})"
            msg += f"#{i}: {name} - Fee: {entry_fee} $TOURS, Pot: {pot} $TOURS, Participants: {int(participants)}, Status: {status}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        logger.info(f"/tournaments listed {count} tournaments, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /tournaments: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error listing tournaments: {str(e)}. Try again! 😅")

async def jointournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /jointournament command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /jointournament command disabled")
        await update.message.reply_text("Tournament joining unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/jointournament failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract:
        logger.error("Web3 not initialized, /jointournament command disabled")
        await update.message.reply_text("Tournament joining unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/jointournament failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 1:
            await update.message.reply_text("Use: /jointournament [id] 🏆")
            logger.info(f"/jointournament failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        tournament_id = int(args[0])
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            logger.info(f"/jointournament failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        checksum_address = w3.to_checksum_address(wallet_address)
        tournament = await contract.functions.tournaments(tournament_id).call()
        entry_fee = tournament[0]
        nonce = await w3.eth.get_transaction_count(checksum_address)
        tx = await contract.functions.joinTournament(tournament_id).build_transaction({
            'from': checksum_address,
            'nonce': nonce,
            'gas': 200000,
            'gas_price': await w3.eth.gas_price,
            'value': 0
        })
        await update.message.reply_text(
            f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for joining tournament #{tournament_id} ({entry_fee / 10**18} $TOURS) using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})).",
            parse_mode="Markdown"
        )
        await set_pending_wallet(user_id, {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": checksum_address,
            "timestamp": time.time()
        })
        logger.info(f"/jointournament transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /jointournament: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def endtournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    logger.info(f"Received /endtournament command from user {update.effective_user.id} in chat {update.effective_chat.id}")
    if not API_BASE_URL:
        logger.error("API_BASE_URL missing, /endtournament command disabled")
        await update.message.reply_text("Tournament ending unavailable due to configuration issues. Try again later! 😅")
        logger.info(f"/endtournament failed due to missing API_BASE_URL, took {time.time() - start_time:.2f} seconds")
        return
    if not w3 or not contract:
        logger.error("Web3 not initialized, /endtournament command disabled")
        await update.message.reply_text("Tournament ending unavailable due to blockchain issues. Try again later! 😅")
        logger.info(f"/endtournament failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Use: /endtournament [id] [winner] 🏆")
            logger.info(f"/endtournament failed due to insufficient args, took {time.time() - start_time:.2f} seconds")
            return
        tournament_id = int(args[0])
        winner_address = args[1]
        session = await get_session(user_id)
        wallet_address = session.get("wallet_address") if session else None
        if not wallet_address:
            await update.message.reply_text("Use /connectwallet! 🪙")
            logger.info(f"/endtournament failed due to missing wallet, took {time.time() - start_time:.2f} seconds")
            return
        checksum_address = w3.to_checksum_address(wallet_address)
        if checksum_address.lower() != OWNER_ADDRESS.lower():
            await update.message.reply_text("Only the owner can end tournaments! 😅")
            logger.info(f"/endtournament failed due to non-owner, took {time.time() - start_time:.2f} seconds")
            return
        winner_checksum_address = w3.to_checksum_address(winner_address)
        nonce = await w3.eth.get_transaction_count(checksum_address)
        tx = await contract.functions.endTournament(tournament_id, winner_checksum_address).build_transaction({
            'from': checksum_address,
            'nonce': nonce,
            'gas': 200000,
            'gas_price': await w3.eth.gas_price,
            'value': 0
        })
        await update.message.reply_text(
            f"Please open or refresh https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for ending tournament #{tournament_id} using your wallet ([{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address})).",
            parse_mode="Markdown"
        )
        await set_pending_wallet(user_id, {
            "awaiting_tx": True,
            "tx_data": tx,
            "wallet_address": checksum_address,
            "timestamp": time.time()
        })
        logger.info(f"/endtournament transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in /endtournament: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

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
            logger.error("Web3 not connected to Monad testnet")
            await update.message.reply_text("Blockchain connection failed. Try again later or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/balance failed due to Web3 connection, took {time.time() - start_time:.2f} seconds")
            return

        # Ensure checksum address
        try:
            checksum_address = w3.to_checksum_address(wallet_address)
        except Exception as e:
            logger.error(f"Error converting wallet address to checksum: {str(e)}")
            await update.message.reply_text(f"Invalid wallet address format: {str(e)}. Try /connectwallet again. 😅")
            logger.info(f"/balance failed due to checksum error, took {time.time() - start_time:.2f} seconds")
            return

        # Check profile status
        profile_status = "No profile"
        try:
            profile = await contract.functions.profiles(checksum_address).call({'gas': 500000})
            logger.info(f"Profile for {checksum_address}: {profile}")
            if profile[0]:
                profile_status = "Profile exists"
            else:
                tours_balance = await tours_contract.functions.balanceOf(checksum_address).call()
                logger.info(f"$TOURS balance for {checksum_address}: {tours_balance / 10**18} $TOURS")
                if tours_balance > 0:
                    profile_status = "Profile likely exists (non-zero $TOURS balance)"
        except Exception as e:
            logger.error(f"Error checking profile or $TOURS balance: {str(e)}")

        # Get balances
        try:
            mon_balance = await w3.eth.get_balance(checksum_address)
            tours_balance = await tours_contract.functions.balanceOf(checksum_address).call()
            await update.message.reply_text(
                f"Wallet Balance:\n"
                f"- {mon_balance / 10**18} $MON\n"
                f"- {tours_balance / 10**18} $TOURS\n"
                f"Address: [{checksum_address}]({EXPLORER_URL}/address/{checksum_address})\n"
                f"Profile Status: {profile_status}\n"
                f"Top up $MON at https://testnet.monad.xyz/faucet",
                parse_mode="Markdown"
            )
            logger.info(f"/balance retrieved for user {user_id}, took {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error retrieving balance for user {user_id}: {str(e)}")
            await update.message.reply_text(f"Failed to retrieve balance: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
            logger.info(f"/balance failed due to balance error, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /balance for user {user_id}: {str(e)}")
        await update.message.reply_text(f"Unexpected error: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        logger.info(f"/balance failed due to unexpected error, took {time.time() - start_time:.2f} seconds")

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

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT location_id, timestamp FROM purchases WHERE wallet_address = $1 ORDER BY timestamp DESC",
                checksum_address
            )

        if not rows:
            await update.message.reply_text("No purchased climbs found. Use /purchaseclimb to buy one! 😅")
            logger.info(f"/mypurchases no purchases found, took {time.time() - start_time:.2f} seconds")
            return

        message = "Your purchased climbs:\n"
        for row in rows:
            if not contract:
                message += f"🏔️ #{row['location_id']} - Purchased {datetime.fromtimestamp(row['timestamp']).strftime('%Y-%m-%d %H:%M')}\n"
                continue
            climb = await contract.functions.getClimbingLocation(row['location_id']).call()
            message += f"🏔️ #{row['location_id']} {escape_html(climb[1])} ({escape_html(climb[2])}) - Purchased {datetime.fromtimestamp(row['timestamp']).strftime('%Y-%m-%d %H:%M')}\n"
            message += f"   Creator: <a href=\"{EXPLORER_URL}/address/{climb[0]}\">{climb[0][:6]}...</a>\n"
            message += f"   Location: ({climb[3]/10**6:.4f}, {climb[4]/10**6:.4f})\n"
            message += f"   Map: https://www.google.com/maps?q={climb[3]/10**6},{climb[4]/10**6}\n"
            message += f"   Photo Hash: {escape_html(climb[5])}\n"
            message += f"   Purchases: {climb[10]}\n\n"

        await update.message.reply_text(message, parse_mode="HTML")
        logger.info(f"/mypurchases success with {len(rows)} purchases, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Unexpected error in /mypurchases: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error retrieving purchases: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅", parse_mode="Markdown")
        
async def handle_tx_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    start_time = time.time()
    user_id = str(update.effective_user.id)
    logger.info(f"Received transaction hash from user {user_id}: {update.message.text} in chat {update.effective_chat.id}")
    pending = await get_pending_wallet(user_id)
    if not pending or not pending.get("awaiting_tx"):
        logger.warning(f"No pending transaction for user {user_id}")
        await update.message.reply_text("No pending transaction found. Use /createprofile, /buyTours, or another command again! 😅")
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
            action = "Action completed"
            if "createProfile" in pending["tx_data"]["data"]:
                action = "Profile created with 1 $TOURS funded to your wallet"
            elif "buyTours" in pending["tx_data"]["data"]:
                amount = int.from_bytes(bytes.fromhex(pending["tx_data"]["data"][10:]), byteorder='big') / 10**18
                action = f"Successfully purchased {amount} $TOURS"
            elif "transfer" in pending["tx_data"]["data"]:
                action = "Successfully sent $TOURS to the recipient"
            elif "createClimbingLocation" in pending["tx_data"]["data"]:
                action = f"Climb '{pending.get('name', 'Unknown')}' ({pending.get('difficulty', 'Unknown')}) created"
            await update.message.reply_text(f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 {action}.", parse_mode="Markdown")
            if CHAT_HANDLE and TELEGRAM_TOKEN:
                message = f"New activity by {escape_html(update.effective_user.username or update.effective_user.first_name)} on EmpowerTours! 🧗 <a href=\"{EXPLORER_URL}/tx/{tx_hash}\">Tx: {escape_html(tx_hash)}</a>"
                await send_notification(CHAT_HANDLE, message)
            if pending.get("next_tx"):
                next_tx_data = pending["next_tx"]
                if next_tx_data["type"] == "create_climbing_location":
                    nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                    tx = await contract.functions.createClimbingLocation(
                        next_tx_data["name"],
                        next_tx_data["difficulty"],
                        next_tx_data["latitude"],
                        next_tx_data["longitude"],
                        next_tx_data["photo_hash"]
                    ).build_transaction({
                        'chainId': 10143,
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
                        f"Approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for climb '{next_tx_data['name']}' ({next_tx_data['difficulty']}) using 10 $TOURS."
                    )
                    logger.info(f"/handle_tx_hash processed approval, next transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
                    return
                elif next_tx_data["type"] == "add_journal_entry":
                    nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                    tx = await contract.functions.addJournalEntryWithDetails(
                        next_tx_data["content_hash"],
                        next_tx_data["location"],
                        next_tx_data["difficulty"],
                        next_tx_data["is_shared"],
                        next_tx_data["cast_hash"]
                    ).build_transaction({
                        'chainId': 10143,
                        'from': pending["wallet_address"],
                        'nonce': nonce,
                        'gas': 500000,
                        'gas_price': await w3.eth.gas_price
                    })
                    await set_pending_wallet(user_id, {
                        "awaiting_tx": True,
                        "tx_data": tx,
                        "wallet_address": pending["wallet_address"],
                        "timestamp": time.time()
                    })
                    await update.message.reply_text(
                        f"Approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for journal entry using 5 $TOURS."
                    )
                    logger.info(f"/handle_tx_hash processed approval, next transaction built for journal, took {time.time() - start_time:.2f} seconds")
                    return
            await delete_pending_wallet(user_id)
            logger.info(f"/handle_tx_hash confirmed for user {user_id}, took {time.time() - start_time:.2f} seconds")
        else:
            await update.message.reply_text("Transaction failed or pending. Check and try again! 😅")
            logger.info(f"/handle_tx_hash failed or pending, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in handle_tx_hash: {str(e)}, took {time.time() - start_time:.2f} seconds")
        await update.message.reply_text(f"Error: {str(e)}. Try again! 😅")

async def monitor_events(context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    global last_processed_block
    if not w3 or not contract:
        logger.error("Web3 or contract not initialized, cannot monitor events")
        logger.info(f"monitor_events failed due to Web3 issues, took {time.time() - start_time:.2f} seconds")
        return
    try:
        latest_block = await w3.eth.get_block_number()
        if last_processed_block == 0:
            last_processed_block = max(0, latest_block - 100)
        batch_size = 100  # Reduced for faster processing; adjust based on testnet latency
        end_block = min(last_processed_block + batch_size, latest_block + 1)
        num_blocks = end_block - last_processed_block - 1
        if num_blocks <= 0:
            logger.info(f"No new blocks to process, took {time.time() - start_time:.2f} seconds")
            return
        logger.info(f"Processing {num_blocks} blocks (from {last_processed_block + 1} to {end_block - 1})")

        # Fetch all logs from the contract in the block range (efficient alternative to per-block fetching)
        logs = await w3.eth.get_logs({
            'fromBlock': last_processed_block + 1,
            'toBlock': end_block - 1,
            'address': w3.to_checksum_address(CONTRACT_ADDRESS)
        })

        # Event map with corrected signatures, hashes, and lambdas (hashes computed from ABI signatures)
        event_map = {
            "b092b68cd4087066d88561f213472db328f688a8993b20e9eab36fee4d6679fd": (  # LocationPurchased(uint256,address,uint256)
                contract.events.LocationPurchased,
                lambda e: f"Climb #{e.args.locationId} purchased by <a href=\"{EXPLORER_URL}/address/{e.args.buyer}\">{e.args.buyer[:6]}...</a> on EmpowerTours! 🪙"
            ),
            "aa3a75c48d1cad3bf60136ab33bc8fd62f31c2b25812d8604da0b7e7fc6d7271": (  # ProfileCreated(address,uint256)
                contract.events.ProfileCreated,
                lambda e: f"New climber joined EmpowerTours! 🧗 Address: <a href=\"{EXPLORER_URL}/address/{e.args.user}\">{e.args.user[:6]}...</a>"
            ),
            "dbf3456d5f59d51cp0e4442bf1c140db5b4b3bd090be958900af45a8310f3deb": (  # ProfileCreatedEnhanced(address,uint256,string,uint256)
                contract.events.ProfileCreatedEnhanced,
                lambda e: f"New climber with Farcaster profile joined EmpowerTours! 🧗 Address: <a href=\"{EXPLORER_URL}/address/{e.args.user}\">{e.args.user[:6]}...</a>"
            ),
            "1f6c34ae7cdb1fe8d152ff37aa480fa0c07f0e0345571e5854cf2b1d4baa75b2": (  # JournalEntryAdded(uint256,address,string,uint256)
                contract.events.JournalEntryAdded,
                lambda e: f"New journal entry #{e.args.entryId} by <a href=\"{EXPLORER_URL}/address/{e.args.author}\">{e.args.author[:6]}...</a> on EmpowerTours! 📝"
            ),
            "8949aebb3586111f1bb264e765b7b0ef7414304cd8c9f061c1c5c56fdcb81862": (  # JournalEntryAddedEnhanced(uint256,address,uint256,string,string,string,bool,uint256)
                contract.events.JournalEntryAddedEnhanced,
                lambda e: f"New enhanced journal entry #{e.args.entryId} by <a href=\"{EXPLORER_URL}/address/{e.args.author}\">{e.args.author[:6]}...</a> on EmpowerTours! 📝"
            ),
            "e22806c8e7df3b9bb5e604a064687dd40d114ccb9b5155678fce0139abf40a2e": (  # CommentAdded(uint256,address,string,uint256)
                contract.events.CommentAdded,
                lambda e: f"New comment on journal #{e.args.entryId} by <a href=\"{EXPLORER_URL}/address/{e.args.commenter}\">{e.args.commenter[:6]}...</a> on EmpowerTours! 🗣️"
            ),
            "0144b9a4c17706f753bf8a43586b92072b9db35f1e038d5c632b9453e38517c7": (  # CommentAddedEnhanced(uint256,address,uint256,string,string,uint256)
                contract.events.CommentAddedEnhanced,
                lambda e: f"New enhanced comment on journal #{e.args.entryId} by <a href=\"{EXPLORER_URL}/address/{e.args.commenter}\">{e.args.commenter[:6]}...</a> on EmpowerTours! 🗣️"
            ),
            "85a125ab0a37494cb20f1e60f7c4b7ba8f6152e82afbe2fd3250ff83ae3363dc": (  # ClimbingLocationCreated(uint256,address,string,uint256)
                contract.events.ClimbingLocationCreated,
                lambda e: f"New climb '{e.args.name}' created by <a href=\"{EXPLORER_URL}/address/{e.args.creator}\">{e.args.creator[:6]}...</a> on EmpowerTours! 🪨"
            ),
            "dd0c2d9cafda4b18e58db06355a912e9ab579dee92649495ae4dc3f0365a269a": (  # ClimbingLocationCreatedEnhanced(uint256,address,uint256,string,string,int256,int256,bool,uint256)
                contract.events.ClimbingLocationCreatedEnhanced,
                lambda e: f"New enhanced climb '{e.args.name}' created by <a href=\"{EXPLORER_URL}/address/{e.args.creator}\">{e.args.creator[:6]}...</a> on EmpowerTours! 🪨"
            ),
            "ad043c04181883ece2f6dc02cf2978a3b453c3d2323bb4bfb95865f910e6c3ce": (  # LocationPurchasedEnhanced(uint256,address,uint256,uint256)
                contract.events.LocationPurchasedEnhanced,
                lambda e: f"Enhanced climb #{e.args.locationId} purchased by <a href=\"{EXPLORER_URL}/address/{e.args.buyer}\">{e.args.buyer[:6]}...</a> on EmpowerTours! 🪙"
            ),
            "d72d415fee16f78aefb0faa7ae3f5221a8d557570c7db32ed71033c7b1717a41": (  # TournamentCreated(uint256,uint256,uint256)
                contract.events.TournamentCreated,
                lambda e: f"New tournament #{e.args.tournamentId} created on EmpowerTours! 🏆"
            ),
            "682cad4379e12a2831600094eb5f795719dea3285c32df028adb89bd2b84a571": (  # TournamentCreatedEmbedded(uint256,address,uint256,string,uint256,uint256)
                contract.events.TournamentCreatedEmbedded,
                lambda e: f"New embedded tournament #{e.args.tournamentId} created by <a href=\"{EXPLORER_URL}/address/{e.args.creator}\">{e.args.creator[:6]}...</a> on EmpowerTours! 🏆"
            ),
            "9b71079da01b6505f63bcd5edd4a7a9dbc55173971019151c9654ae29def6bac": (  # TournamentJoined(uint256,address)
                contract.events.TournamentJoined,
                lambda e: f"Climber <a href=\"{EXPLORER_URL}/address/{e.args.participant}\">{e.args.participant[:6]}...</a> joined tournament #{e.args.tournamentId} on EmpowerTours! 🏆"
            ),
            "2cccfd0c70d5149159c82c9c2d66f2a9874ec2356c5c0788087ec7313916e02e": (  # TournamentJoinedEnhanced(uint256,address,uint256)
                contract.events.TournamentJoinedEnhanced,
                lambda e: f"Climber <a href=\"{EXPLORER_URL}/address/{e.args.participant}\">{e.args.participant[:6]}...</a> joined enhanced tournament #{e.args.tournamentId} on EmpowerTours! 🏆"
            ),
            "dd7ad4d17119eef4327e49ef4368c3d112ab5b71ee7918afcadc779b78eed9d9": (  # TournamentEnded(uint256,address,uint256)
                contract.events.TournamentEnded,
                lambda e: f"Tournament #{e.args.tournamentId} ended! Winner: <a href=\"{EXPLORER_URL}/address/{e.args.winner}\">{e.args.winner[:6]}...</a> Prize: {e.args.pot / 10**18} $TOURS 🏆"
            ),
            "f0f0525a5ef10132058aa9a3feb1a1f6d503037788ea59f454076e216da1a741": (  # TournamentEndedEnhanced(uint256,address,uint256,uint256)
                contract.events.TournamentEndedEnhanced,
                lambda e: f"Enhanced tournament #{e.args.tournamentId} ended! Winner: <a href=\"{EXPLORER_URL}/address/{e.args.winner}\">{e.args.winner[:6]}...</a> Prize: {e.args.pot / 10**18} $TOURS 🏆"
            ),
            "b9f217daf6aa350a9b78812562d0d1afba9439b7b595919c7d9dfc40d2230f35": (  # FarcasterCastShared(address,uint256,string,string,uint256,uint256)
                contract.events.FarcasterCastShared,
                lambda e: f"New Farcaster cast shared by <a href=\"{EXPLORER_URL}/address/{e.args.user}\">{e.args.user[:6]}...</a> for {e.args.contentType} #{e.args.contentId} on EmpowerTours! 📢"
            ),
            "32838cd85a2abed5fd25bfdd6952f7f1d0ca533b1eb897506a812c5ea0a99612": (  # FarcasterProfileUpdated(address,uint256,string,string,uint256)
                contract.events.FarcasterProfileUpdated,
                lambda e: f"Farcaster profile updated by <a href=\"{EXPLORER_URL}/address/{e.args.user}\">{e.args.user[:6]}...</a> on EmpowerTours! 📢"
            ),
            "7c041c6a61b05a6a99f81f2f3338d3911721f95ec7da19a69782e5a887e1340f": (  # ToursPurchased(address,uint256,uint256)
                contract.events.ToursPurchased,
                lambda e: f"User <a href=\"{EXPLORER_URL}/address/{e.args.buyer}\">{e.args.buyer[:6]}...</a> bought {e.args.toursAmount / 10**18} $TOURS on EmpowerTours! 🪙"
            ),
        }

        for log in logs:
            try:
                topic0 = log['topics'][0].hex()
                if topic0 in event_map:
                    event_class, message_fn = event_map[topic0]
                    event = event_class().process_log(log)
                    message = message_fn(event)
                    # Auto-announce to group
                    await send_notification(CHAT_HANDLE, message)
                    # New: PM user if wallet matches an event arg
                    user_address = event.args.get('user') or event.args.get('creator') or event.args.get('author') or event.args.get('buyer') or event.args.get('commenter') or event.args.get('participant') or event.args.get('winner')
                    if user_address:
                        checksum_user_address = w3.to_checksum_address(user_address)
                        if checksum_user_address in reverse_sessions:
                            user_id = reverse_sessions[checksum_user_address]
                            user_message = f"Your action succeeded! {message.replace('<a href=', '[Tx: ').replace('</a>', ']')} 🪙 Check details on {EXPLORER_URL}/tx/{log['transactionHash'].hex()}"
                            await application.bot.send_message(user_id, user_message, parse_mode="Markdown")
                    # Store purchase in DB if LocationPurchased
                    if topic0 == "b092b68cd4087066d88561f213472db328f688a8993b20e9eab36fee4d6679fd":  # LocationPurchased(uint256,address,uint256)
                        buyer = event.args.buyer
                        checksum_buyer = w3.to_checksum_address(buyer)
                        if checksum_buyer in reverse_sessions:
                            user_id = reverse_sessions[checksum_buyer]
                            async with pool.acquire() as conn:
                                await conn.execute(
                                    "INSERT INTO purchases (user_id, wallet_address, location_id, timestamp) VALUES ($1, $2, $3, $4)",
                                    user_id, checksum_buyer, event.args.locationId, event.args.timestamp
                                )
            except Exception as e:
                logger.error(f"Error processing log: {str(e)}")

        last_processed_block = end_block - 1
        logger.info(f"Processed events up to block {last_processed_block}, took {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in monitor_events: {str(e)}, took {time.time() - start_time:.2f} seconds")

async def get_session(user_id):
    return sessions.get(user_id)

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
    
async def set_session(user_id, wallet_address):
    global sessions, reverse_sessions
    sessions[user_id] = {"wallet_address": wallet_address}
    if wallet_address:
        reverse_sessions[wallet_address] = user_id
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, wallet_address) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET wallet_address = $2",
            user_id, wallet_address
        )

async def get_pending_wallet(user_id):
    return pending_wallets.get(user_id)

async def set_pending_wallet(user_id, data):
    global pending_wallets
    pending_wallets[user_id] = data
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO pending_wallets (user_id, data, timestamp) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET data = $2, timestamp = $3",
            user_id, json.dumps(data), data['timestamp']
        )

async def delete_pending_wallet(user_id):
    global pending_wallets
    if user_id in pending_wallets:
        del pending_wallets[user_id]
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pending_wallets WHERE user_id = $1", user_id)

async def get_journal_data(user_id):
    return journal_data.get(user_id)

async def set_journal_data(user_id, data):
    global journal_data
    journal_data[user_id] = data
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO journal_data (user_id, data, timestamp) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET data = $2, timestamp = $3",
            user_id, json.dumps(data), data['timestamp']
        )
async def get_purchase_events(wallet_address, from_block, to_block, step=500):  # Reduced step to avoid 413
    events = []
    for start in range(from_block, to_block + 1, step):
        end = min(start + step - 1, to_block)
        try:
            event_filter = await contract.events.LocationPurchased.create_filter(
                fromBlock=start,
                toBlock=end,
                argument_filters={'buyer': wallet_address} if wallet_address else None
            )
            batch_events = await event_filter.get_all_entries()
            events.extend(batch_events)
        except Exception as e:
            logger.warning(f"Error fetching events for batch {start}-{end}: {str(e)}. Skipping batch.")
        await asyncio.sleep(0.1)  # Small delay to avoid rate limiting
    return events
    
async def delete_journal_data(user_id):
    global journal_data
    if user_id in journal_data:
        del journal_data[user_id]
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM journal_data WHERE user_id = $1", user_id)

async def startup_event():
    start_time = time.time()
    global application, webhook_failed, pool, sessions, reverse_sessions, pending_wallets, journal_data
    try:
        # Initialize Postgres pool
        pool = await asyncpg.create_pool(DATABASE_URL)
        async with pool.acquire() as conn:
            # Create tables
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                wallet_address TEXT
            )
            """)
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_wallets (
                user_id TEXT PRIMARY KEY,
                data JSONB,
                timestamp FLOAT
            )
            """)
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS journal_data (
                user_id TEXT PRIMARY KEY,
                data JSONB,
                timestamp FLOAT
            )
            """)
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS media_files (
                hash TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                entry_id INTEGER
            )
            """)
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                user_id TEXT,
                wallet_address TEXT,
                location_id INTEGER,
                timestamp INTEGER
            )
            """)

            # Load data
            rows = await conn.fetch("SELECT * FROM users")
            sessions = {}
            reverse_sessions = {}
            for row in rows:
                sessions[row['user_id']] = {"wallet_address": row['wallet_address']}
                if row['wallet_address']:
                    reverse_sessions[row['wallet_address']] = row['user_id']

            rows = await conn.fetch("SELECT * FROM pending_wallets")
            pending_wallets = {}
            current_time = time.time()
            for row in rows:
                if current_time - row['timestamp'] < 3600:
                    pending_wallets[row['user_id']] = json.loads(row['data'])
                    pending_wallets[row['user_id']]['timestamp'] = row['timestamp']

            rows = await conn.fetch("SELECT * FROM journal_data")
            journal_data = {}
            for row in rows:
                if current_time - row['timestamp'] < 3600:
                    journal_data[row['user_id']] = json.loads(row['data'])
                    journal_data[row['user_id']]['timestamp'] = row['timestamp']

            logger.info(f"Loaded from DB: {len(sessions)} sessions, {len(pending_wallets)} pending_wallets, {len(journal_data)} journal_data")

        # One-time historical backfill for purchases
        if w3 and contract:
            logger.info("Starting historical backfill for LocationPurchased events")
            latest_block = await w3.eth.get_block_number()
            all_events = await get_purchase_events(None, 0, latest_block)  # No buyer filter for full backfill
            async with pool.acquire() as conn:
                for event in all_events:
                    checksum_buyer = w3.to_checksum_address(event.args.buyer)
                    if checksum_buyer in reverse_sessions:
                        user_id = reverse_sessions[checksum_buyer]
                        await conn.execute(
                            "INSERT INTO purchases (user_id, wallet_address, location_id, timestamp) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                            user_id, checksum_buyer, event.args.locationId, event.args.timestamp
                        )
            logger.info(f"Backfill complete: Processed {len(all_events)} events")

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
        application.add_handler(CommandHandler("createprofile", create_profile))
        application.add_handler(CommandHandler("help", help))
        application.add_handler(CommandHandler("journal", journal_entry))
        application.add_handler(CommandHandler("comment", add_comment))
        application.add_handler(CommandHandler("buildaclimb", buildaclimb))
        application.add_handler(CommandHandler("purchaseclimb", purchase_climb))
        application.add_handler(CommandHandler("findaclimb", findaclimb))
        application.add_handler(CommandHandler("journals", journals))
        application.add_handler(CommandHandler("viewjournal", viewjournal))
        application.add_handler(CommandHandler("viewclimb", viewclimb))
        application.add_handler(CommandHandler("mypurchases", mypurchases))
        application.add_handler(CommandHandler("createtournament", createtournament))
        application.add_handler(CommandHandler("tournaments", tournaments))
        application.add_handler(CommandHandler("jointournament", jointournament))
        application.add_handler(CommandHandler("endtournament", endtournament))
        application.add_handler(CommandHandler("balance", balance))
        application.add_handler(CommandHandler("buyTours", buy_tours))
        application.add_handler(CommandHandler("sendTours", send_tours))
        application.add_handler(CommandHandler("ping", ping))
        application.add_handler(CommandHandler("debug", debug))
        application.add_handler(CommandHandler("forcewebhook", forcewebhook))
        application.add_handler(CommandHandler("clearcache", clearcache))
        application.add_handler(MessageHandler(filters.Regex(r'^0x[a-fA-F0-9]{64}$'), handle_tx_hash))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.LOCATION, handle_location))
        application.add_handler(MessageHandler(filters.COMMAND, unknown_command))  # Changed to unknown_command
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
        logger.info("Command handlers registered successfully")

        # Schedule monitor_events with 60-second interval
        if application.job_queue:
            logger.info("JobQueue available, scheduling monitor_events")
            application.job_queue.run_repeating(monitor_events, interval=30, first=10)
        else:
            logger.warning("JobQueue not available, monitor_events not scheduled")

        # Initialize and start application
        await application.initialize()
        logger.info("Application initialized via initialize()")

        # Set bot commands
        commands = [
            BotCommand("start", "Welcome message"),
            BotCommand("tutorial", "Setup guide"),
            BotCommand("connectwallet", "Connect your wallet"),
            BotCommand("createprofile", "Create profile"),
            BotCommand("help", "List all commands"),
            BotCommand("journal", "Log a climb"),
            BotCommand("comment", "Comment on a journal"),
            BotCommand("buildaclimb", "Create a new climb"),
            BotCommand("purchaseclimb", "Buy a climb"),
            BotCommand("findaclimb", "List available climbs"),
            BotCommand("journals", "List all journal entries"),
            BotCommand("viewjournal", "View a journal entry"),
            BotCommand("viewclimb", "View a specific climb"),
            BotCommand("mypurchases", "View your purchased climbs"),
            BotCommand("createtournament", "Start a tournament"),
            BotCommand("tournaments", "List all tournaments"),
            BotCommand("jointournament", "Join a tournament"),
            BotCommand("endtournament", "End a tournament (owner only)"),
            BotCommand("balance", "Check your $MON and $TOURS balance"),
            BotCommand("buytours", "Buy $TOURS tokens"),
            BotCommand("sendtours", "Send $TOURS to another wallet"),
            BotCommand("ping", "Check if the bot is running"),
            BotCommand("debug", "Debug webhook status"),
            BotCommand("forcewebhook", "Force reset webhook"),
            BotCommand("clearcache", "Clear Telegram cache")
        ]
        await application.bot.set_my_commands(commands)
        logger.info(f"Set {len(commands)} bot commands successfully")

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
    global application, pool
    logger.info("Received shutdown signal")
    if application:
        try:
            await application.stop()
            await application.updater.stop()
            logger.info(f"Application shutdown complete, took {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}, took {time.time() - start_time:.2f} seconds")
    if pool:
        await pool.close()
        logger.info("Postgres pool closed")

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
            await application.bot.send_message(user_id, "Invalid wallet address or blockchain unavailable. Try /connectwallet again. 😅")
            logger.info(f"/submit_wallet failed due to invalid address or Web3, took {time.time() - start_time:.2f} seconds")
            return {"status": "error"}
        
        # Process wallet even if not in pending_wallets to handle edge cases
        pending = await get_pending_wallet(user_id)
        if not pending or not pending.get("awaiting_wallet"):
            logger.warning(f"No pending wallet connection for user {user_id}, proceeding anyway")
        
        try:
            checksum_address = w3.to_checksum_address(wallet_address)
            await set_session(user_id, checksum_address)
            await application.bot.send_message(
                user_id,
                f"Wallet [{checksum_address[:6]}...]({EXPLORER_URL}/address/{checksum_address}) connected! Use /createprofile to create your profile or /balance to check your status. 🪙",
                parse_mode="Markdown"
            )
            await delete_pending_wallet(user_id)
            logger.info(f"/submit_wallet processed for user {user_id}, wallet {checksum_address}, took {time.time() - start_time:.2f} seconds")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error processing wallet address for user {user_id}: {str(e)}")
            await application.bot.send_message(user_id, f"Error connecting wallet: {str(e)}. Try /connectwallet again. 😅")
            return {"status": "error"}
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
                    input_data = pending.get("tx_data", {}).get("data", "")
                    success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 Action completed successfully."
                    if input_data.startswith('0x00547664'):  # createProfile
                        success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 Profile created with 1 $TOURS funded to your wallet."
                    elif input_data.startswith('0x9954e40d'):  # buyTours
                        amount = int.from_bytes(bytes.fromhex(input_data[10:]), byteorder='big') / 10**18
                        success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 Successfully purchased {amount} $TOURS."
                    elif input_data.startswith('0xa9059cbb'):  # transfer (sendTours)
                        success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 Successfully sent $TOURS to the recipient."
                    elif input_data.startswith('0xfe985ae0'):  # createClimbingLocation
                        success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 Climb '{pending.get('name', 'Unknown')}' ({pending.get('difficulty', 'Unknown')}) created!"
                    elif input_data.startswith('0x6b8b0b0a'):  # addJournalEntryWithDetails, check the selector
                        success_message = f"Transaction confirmed! [Tx: {tx_hash}]({EXPLORER_URL}/tx/{tx_hash}) 🪙 Journal entry added!"
                    if CHAT_HANDLE and TELEGRAM_TOKEN:
                        message = f"New activity by user {user_id} on EmpowerTours! 🧗 <a href=\"{EXPLORER_URL}/tx/{tx_hash}\">Tx: {escape_html(tx_hash)}</a>"
                        await send_notification(CHAT_HANDLE, message)
                    await application.bot.send_message(user_id, success_message, parse_mode="Markdown")
                    entry_type = pending.get('entry_type')
                    photo_hash = pending.get('photo_hash')
                    if entry_type and photo_hash:
                        if entry_type == 'journal':
                            entry_id = await contract.functions.getJournalEntryCount().call() - 1
                        elif entry_type == 'climb':
                            entry_id = await contract.functions.getClimbingLocationCount().call() - 1
                        async with pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE media_files SET entry_id = $1 WHERE hash = $2",
                                entry_id, photo_hash
                            )
                    if pending.get("next_tx"):
                        next_tx_data = pending["next_tx"]
                        if next_tx_data["type"] == "create_climbing_location":
                            nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                            tx = await contract.functions.createClimbingLocation(
                                next_tx_data["name"],
                                next_tx_data["difficulty"],
                                next_tx_data["latitude"],
                                next_tx_data["longitude"],
                                next_tx_data["photo_hash"]
                            ).build_transaction({
                                'chainId': 10143,
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
                                f"Approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for climb '{next_tx_data['name']}' ({next_tx_data['difficulty']}) using 10 $TOURS."
                            )
                            logger.info(f"/submit_tx processed approval, next transaction built for user {user_id}, took {time.time() - start_time:.2f} seconds")
                            return {"status": "success"}
                        elif next_tx_data["type"] == "add_journal_entry":
                            nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                            tx = await contract.functions.addJournalEntryWithDetails(
                                next_tx_data["content_hash"],
                                next_tx_data["location"],
                                next_tx_data["difficulty"],
                                next_tx_data["is_shared"],
                                next_tx_data["cast_hash"]
                            ).build_transaction({
                                'chainId': 10143,
                                'from': pending["wallet_address"],
                                'nonce': nonce,
                                'gas': 500000,
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
                                f"Approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for journal entry using 5 $TOURS."
                            )
                            logger.info(f"/submit_tx processed approval, next transaction built for journal, took {time.time() - start_time:.2f} seconds")
                            return {"status": "success"}
                        elif next_tx_data["type"] == "purchase_climbing_location":
                            nonce = await w3.eth.get_transaction_count(pending["wallet_address"])
                            tx = await contract.functions.purchaseClimbingLocation(next_tx_data["location_id"]).build_transaction({
                                'from': pending["wallet_address"],
                                'nonce': nonce,
                                'gas': 200000,
                                'gas_price': await w3.eth.gas_price,
                                'value': 0
                            })
                            await set_pending_wallet(user_id, {
                                "awaiting_tx": True,
                                "tx_data": tx,
                                "wallet_address": pending["wallet_address"],
                                "timestamp": time.time()
                            })
                            await application.bot.send_message(
                                user_id,
                                f"Approval confirmed! Now open https://version1-production.up.railway.app/public/connect.html?userId={user_id} to sign the transaction for purchasing climb #{next_tx_data['location_id']} using 10 $TOURS."
                            )
                            logger.info(f"/submit_tx processed approval, next transaction built for purchase_climb, took {time.time() - start_time:.2f} seconds")
                            return {"status": "success"}
                    await delete_pending_wallet(user_id)
                logger.info(f"/submit_tx confirmed for user {user_id}, took {time.time() - start_time:.2f} seconds")
                return {"status": "success"}
            else:
                # Check for specific revert reasons
                try:
                    tx = await w3.eth.get_transaction(tx_hash)
                    input_data = tx['input']
                    if input_data.startswith('0x00547664'):  # createProfile
                        await contract.functions.createProfile().call({
                            'from': tx['from'],
                            'value': tx['value'],
                            'gas': tx['gas']
                        })
                    elif input_data.startswith('0x9954e40d'):  # buyTours
                        amount = int.from_bytes(input_data[4:], byteorder='big')
                        await contract.functions.buyTours(amount).call({
                            'from': tx['from'],
                            'value': tx['value'],
                            'gas': tx['gas']
                        })
                    elif input_data.startswith('0xa9059cbb'):  # transfer (sendTours)
                        recipient = '0x' + input_data[34:74]
                        amount = int.from_bytes(input_data[74:], byteorder='big') / 10**18
                        await tours_contract.functions.transfer(recipient, amount * 10**18).call({
                            'from': tx['from'],
                            'gas': tx['gas']
                        })
                    elif input_data.startswith('0xfe985ae0'):  # createClimbingLocation
                        name = w3.to_text(bytes.fromhex(input_data[74:138])).rstrip('\x00')
                        difficulty = w3.to_text(bytes.fromhex(input_data[202:234])).rstrip('\x00')
                        latitude = int.from_bytes(bytes.fromhex(input_data[138:170]), byteorder='big', signed=True)
                        longitude = int.from_bytes(bytes.fromhex(input_data[170:202]), byteorder='big', signed=True)
                        photo_hash = w3.to_text(bytes.fromhex(input_data[266:])).rstrip('\x00')
                        await contract.functions.createClimbingLocation(name, difficulty, latitude, longitude, photo_hash).call({
                            'from': tx['from'],
                            'gas': tx['gas']
                        })
                    else:
                        raise Exception("Unknown function call")
                except Exception as e:
                    revert_reason = str(e)
                    logger.error(f"Transaction {tx_hash} reverted: {revert_reason}")
                    if "ProfileExists" in revert_reason:
                        await application.bot.send_message(
                            user_id,
                            f"Transaction failed: Profile already exists for wallet [{tx['from'][:6]}...]({EXPLORER_URL}/address/{tx['from']})! Use /balance to check your status or try commands like /journal or /buildaclimb. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                            parse_mode="Markdown"
                        )
                    elif "ProfileRequired" in revert_reason:
                        await application.bot.send_message(
                            user_id,
                            f"Transaction failed: Profile is required. Use /createprofile first, then try again. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                            parse_mode="Markdown"
                        )
                    elif "InsufficientMonSent" in revert_reason:
                        await application.bot.send_message(
                            user_id,
                            f"Transaction failed: Insufficient $MON sent. Top up at https://testnet.monad.xyz/faucet and try again. 😅"
                        )
                    elif "InsufficientTokenBalance" in revert_reason:
                        await application.bot.send_message(
                            user_id,
                            f"Transaction failed: Insufficient $TOURS. Use /buyTours to get more $TOURS. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                            parse_mode="Markdown"
                        )
                    elif "InvalidLocationId" in revert_reason or "InvalidEntryId" in revert_reason:
                        await application.bot.send_message(
                            user_id,
                            f"Transaction failed: Invalid climb or entry ID. Check with /findaclimb or /journals and try again. Contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                            parse_mode="Markdown"
                        )
                    else:
                        await application.bot.send_message(
                            user_id,
                            f"Transaction failed: {revert_reason}. Check parameters or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                            parse_mode="Markdown"
                        )
                logger.info(f"/submit_tx failed or pending for user {user_id}, took {time.time() - start_time:.2f} seconds")
                raise HTTPException(status_code=400, detail="Transaction failed or pending")
        except Exception as e:
            logger.error(f"Error verifying transaction for user {user_id}: {str(e)}, took {time.time() - start_time:.2f} seconds")
            await application.bot.send_message(
                user_id,
                f"Error verifying transaction: {str(e)}. Try again or contact support at [EmpowerTours Chat](https://t.me/empowertourschat). 😅",
                parse_mode="Markdown"
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
