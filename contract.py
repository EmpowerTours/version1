import os
import json
from web3 import Web3
from web3.exceptions import ContractLogicError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
MONAD_RPC_URL = os.getenv("MONAD_RPC_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
TOURS_TOKEN_ADDRESS = os.getenv("TOURS_TOKEN_ADDRESS")
OWNER_ADDRESS = os.getenv("OWNER_ADDRESS")
LEGACY_ADDRESS = os.getenv("LEGACY_ADDRESS")
CHAT_HANDLE = "@empowertourschat"

# Connect to Monad testnet
w3 = Web3(Web3.HTTPProvider(MONAD_RPC_URL))

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

async def get_gas_fees(wallet_address):
    try:
        base_fee = w3.eth.get_block('latest')['baseFeePerGas']
        max_priority_fee = w3.eth.max_priority_fee
        max_fee_per_gas = base_fee + max_priority_fee
        return {
            'maxFeePerGas': max_fee_per_gas,
            'maxPriorityFeePerGas': max_priority_fee
        }
    except Exception as e:
        return {
            'maxFeePerGas': w3.to_wei('2', 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei('1', 'gwei')
        }

async def create_profile_tx(wallet_address, user):
    try:
        profile = contract.functions.profiles(wallet_address).call()
        if profile[0]:
            return {'status': 'error', 'message': f"Profile already exists for {wallet_address}! Try /journal or /buildaclimb. 🪨"}
        
        profile_fee = contract.functions.profileFee().call()
        balance = w3.eth.get_balance(wallet_address)
        gas_estimate = contract.functions.createProfile().estimate_gas({'from': wallet_address, 'value': profile_fee})
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
        
        nonce = w3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.createProfile().build_transaction({
            'chainId': 10143,
            'from': wallet_address,
            'value': profile_fee,
            'nonce': nonce,
            'gas': gas_limit,
            'maxFeePerGas': gas_fees['maxFeePerGas'],
            'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
        })
        return {'status': 'success', 'tx_data': tx}
    except ContractLogicError as e:
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the contract is valid or try again later. 😅"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def add_journal_entry_tx(wallet_address, content_hash, user):
    try:
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
        return {'status': 'success', 'tx_data': tx}
    except ContractLogicError as e:
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure you have a profile and try again. 😅"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def add_comment_tx(wallet_address, entry_id, comment, user):
    try:
        comment_hash = w3.keccak(text=comment).hex()
        comment_fee = contract.functions.commentFee().call()
        balance = w3.eth.get_balance(wallet_address)
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
        return {'status': 'success', 'tx_data': tx}
    except ContractLogicError as e:
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the entry exists and you have enough $MON. 😅"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def create_climbing_location_tx(wallet_address, name, difficulty, latitude, longitude, photo_hash, user):
    try:
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
        return {'status': 'success', 'tx_type': 'create_climbing_location', 'tx_data': tx}
    except ContractLogicError as e:
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure you have a profile and sufficient $TOURS allowance. 😅"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def purchase_climbing_location_tx(wallet_address, location_id, user):
    try:
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
            return {
                'status': 'success',
                'tx_type': 'approve_tours',
                'tx_data': approve_tx,
                'next_tx': {
                    'type': 'purchase_climbing_location',
                    'location_id': location_id
                }
            }
        
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
        return {'status': 'success', 'tx_type': 'purchase_climbing_location', 'tx_data': tx}
    except ContractLogicError as e:
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the location ID is valid. 😅"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def create_tournament_tx(wallet_address, entry_fee, user):
    try:
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
        return {'status': 'success', 'tx_data': tx}
    except ContractLogicError as e:
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure you have a profile. 😅"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def join_tournament_tx(wallet_address, tournament_id, user):
    try:
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
            return {
                'status': 'success',
                'tx_type': 'approve_tours',
                'tx_data': approve_tx,
                'next_tx': {
                    'type': 'join_tournament',
                    'tournament_id': tournament_id
                }
            }
        
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
        return {'status': 'success', 'tx_type': 'join_tournament', 'tx_data': tx}
    except ContractLogicError as e:
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the tournament ID is valid. 😅"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def end_tournament_tx(wallet_address, tournament_id, winner_address, user):
    try:
        if wallet_address.lower() != OWNER_ADDRESS.lower():
            return {'status': 'error', 'message': "Only the owner can end tournaments! 🚫"}
        if not w3.is_address(winner_address):
            return {'status': 'error', 'message': "Invalid winner address! 😕"}
        
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
        return {'status': 'success', 'tx_data': tx}
    except ContractLogicError as e:
        return {'status': 'error', 'message': f"Contract error: {str(e)}. Ensure the tournament ID is valid. 😅"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}

async def get_climbing_locations():
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
        return []

async def broadcast_transaction(signed_tx_hex, pending_tx, user, context):
    try:
        tx_hash = w3.eth.send_raw_transaction(signed_tx_hex)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        
        if receipt.status == 1:
            if pending_tx['type'] == 'create_profile':
                return {
                    'status': 'success',
                    'message': (
                        f"Welcome aboard, {user.first_name}! Your profile is live! 🎉 Tx: {tx_hash.hex()}\n"
                        "Try /journal to log your first climb or /buildaclimb to share a spot! 🪨"
                    ),
                    'group_message': f"New climber {user.username} joined EmpowerTours! 🧗 Tx: {tx_hash.hex()}"
                }
            elif pending_tx['type'] == 'journal_entry':
                return {
                    'status': 'success',
                    'message': f"Journal entry logged, {user.first_name}! You earned 5 $TOURS! 🎉 Tx: {tx_hash.hex()}",
                    'group_message': f"{user.username} shared a climb journal! 🪨 Check it out! Tx: {tx_hash.hex()}"
                }
            elif pending_tx['type'] == 'approve_tours' and 'next_tx' in pending_tx:
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
                        'gas': int(pending_tx['tx_data']['gas'] * 1.2),
                        'maxFeePerGas': gas_fees['maxFeePerGas'],
                        'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
                    })
                    pending_tx.update({
                        'type': 'create_climbing_location',
                        'tx_data': next_tx
                    })
                    return {
                        'status': 'success',
                        'message': (
                            f"$TOURS approval successful! Now copy this transaction to your wallet:\n"
                            f"```json\n{json.dumps(next_tx, indent=2)}\n```\n"
                            f"Or scan the QR code to import it. After signing, submit with /sendtx <signed_tx_hex>. 🪙"
                        ),
                        'tx_data': next_tx
                    }
                elif next_tx_type == 'purchase_climbing_location':
                    next_tx = contract.functions.purchaseClimbingLocation(
                        pending_tx['next_tx']['location_id']
                    ).build_transaction({
                        'chainId': 10143,
                        'from': pending_tx['wallet_address'],
                        'nonce': nonce,
                        'gas': int(pending_tx['tx_data']['gas'] * 1.2),
                        'maxFeePerGas': gas_fees['maxFeePerGas'],
                        'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
                    })
                    pending_tx.update({
                        'type': 'purchase_climbing_location',
                        'location_id': pending_tx['next_tx']['location_id'],
                        'tx_data': next_tx
                    })
                    return {
                        'status': 'success',
                        'message': (
                            f"$TOURS approval successful! Now copy this transaction to your wallet:\n"
                            f"```json\n{json.dumps(next_tx, indent=2)}\n```\n"
                            f"Or scan the QR code to import it. After signing, submit with /sendtx <signed_tx_hex>. 🪙"
                        ),
                        'tx_data': next_tx
                    }
                elif next_tx_type == 'join_tournament':
                    next_tx = contract.functions.joinTournament(
                        pending_tx['next_tx']['tournament_id']
                    ).build_transaction({
                        'chainId': 10143,
                        'from': pending_tx['wallet_address'],
                        'nonce': nonce,
                        'gas': int(pending_tx['tx_data']['gas'] * 1.2),
                        'maxFeePerGas': gas_fees['maxFeePerGas'],
                        'maxPriorityFeePerGas': gas_fees['maxPriorityFeePerGas']
                    })
                    pending_tx.update({
                        'type': 'join_tournament',
                        'tournament_id': pending_tx['next_tx']['tournament_id'],
                        'tx_data': next_tx
                    })
                    return {
                        'status': 'success',
                        'message': (
                            f"$TOURS approval successful! Now copy this transaction to your wallet:\n"
                            f"```json\n{json.dumps(next_tx, indent=2)}\n```\n"
                            f"Or scan the QR code to import it. After signing, submit with /sendtx <signed_tx_hex>. 🪙"
                        ),
                        'tx_data': next_tx
                    }
            elif pending_tx['type'] == 'create_climbing_location':
                location_id = contract.functions.getClimbingLocationCount().call() - 1
                location = contract.functions.climbingLocations(location_id).call()
                return {
                    'status': 'success',
                    'message': (
                        f"Climb created, {user.first_name}! 🪨 {pending_tx['name']} ({pending_tx['difficulty']}) "
                        f"at ({location[3]/10**6:.4f}, {location[4]/10**6:.4f}). Tx: {tx_hash.hex()}"
                    ),
                    'group_message': (
                        f"New climb by {user.username}! 🧗\n"
                        f"Name: {pending_tx['name']} ({pending_tx['difficulty']})\n"
                        f"Location: ({location[3]/10**6:.4f}, {location[4]/10**6:.4f})\n"
                        f"Tx: {tx_hash}"
                    )
                }
            elif pending_tx['type'] == 'purchase_climbing_location':
                return {
                    'status': 'success',
                    'message': f"Climb #{pending_tx['location_id']} purchased, {user.first_name}! 🎉 Tx: {tx_hash.hex()}",
                    'group_message': f"{user.username} purchased climb #{pending_tx['location_id']}! 🪨 Tx: {tx_hash.hex()}"
                }
            elif pending_tx['type'] == 'create_tournament':
                tournament_id = contract.functions.getTournamentCount().call() - 1
                return {
                    'status': 'success',
                    'message': f"Tournament #{tournament_id} created, {user.first_name}! 🏆 Tx: {tx_hash.hex()}",
                    'group_message': (
                        f"New tournament #{tournament_id} by {user.username}! 🏆\n"
                        f"Join with /jointournament {tournament_id}\n"
                        f"Tx: {tx_hash.hex()}"
                    )
                }
            elif pending_tx['type'] == 'join_tournament':
                return {
                    'status': 'success',
                    'message': f"Joined tournament #{pending_tx['tournament_id']}, {user.first_name}! 🏆 Tx: {tx_hash.hex()}",
                    'group_message': f"{user.username} joined tournament #{pending_tx['tournament_id']}! 🏆 Tx: {tx_hash.hex()}"
                }
            elif pending_tx['type'] == 'end_tournament':
                return {
                    'status': 'success',
                    'message': f"Tournament #{pending_tx['tournament_id']} ended, {user.first_name}! 🏆 Tx: {tx_hash.hex()}",
                    'group_message': f"Tournament #{pending_tx['tournament_id']} ended by {user.username}! 🏆 Tx: {tx_hash.hex()}"
                }
        else:
            return {'status': 'error', 'message': "Transaction failed. Ensure the signed transaction is valid and try again! 💪"}
    except Exception as e:
        return {'status': 'error', 'message': f"Oops, something went wrong: {str(e)}. Try again! 😅"}
