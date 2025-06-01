import os
import secrets
from flask import Flask, request, jsonify, make_response
import firebase_admin
from firebase_admin import credentials, firestore
import random
import string
import time
import copy
from functools import wraps
from cards import CARDS, DECK_COMPOSITION, create_deck


# Initialize Firebase Admin SDK
cred = credentials.Certificate('vegan-cardgame-firebase-adminsdk-fbsvc-b2013bb175.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def verify_player_turn(room_data, player_token, expected_state=None):
    """Helper function to verify player's turn and game state.
    
    Args:
        room_data: The room data dictionary or DocumentSnapshot
        player_token: The player's authentication token
        expected_state: Optional expected game state to verify
        
    Returns:
        tuple: (player_number, None, None) if verification passes
               (None, error_response, status_code) if verification fails
    """
    # Convert DocumentSnapshot to dict if needed
    if hasattr(room_data, 'to_dict'):
        room_data = room_data.to_dict()
    
    # Verify player token and determine player number (1 or 2)
    players = room_data.get('players', [])
    player = None
    for i, p in enumerate(players, 1):
        if p.get('token') == player_token:
            player = i
            break
    
    if not player:
        return None, {'error': 'Invalid player token'}, 403
        
    # Verify it's the player's turn
    current_turn = room_data.get('current_turn')
    if current_turn != player:
        return None, {'error': 'Not your turn'}, 403
        
    # Verify game state if expected_state is provided
    if expected_state and room_data.get('game_state') != expected_state:
        return None, {'error': f'Invalid game state. Expected: {expected_state}'}, 400
        
    return player, None, None

def filter_game_data_for_player(game_data, player_number):
    """
    Filter game data to only show information visible to the requesting player.
    
    Args:
        game_data (dict): The complete game data from Firestore
        player_number (int): The player number (1 or 2) making the request
        
    Returns:
        dict: Filtered game data with hidden information removed
    """
    if not game_data:
        return {}
        
    # Create a deep copy to avoid modifying the original
    filtered_data = copy.deepcopy(game_data)
    
    # Determine opponent number
    opponent_number = 2 if player_number == 1 else 1
    
    # Hide opponent's hand but keep the image field
    if 'players' in filtered_data and len(filtered_data['players']) >= opponent_number:
        opponent_index = opponent_number - 1
        if 'hand' in filtered_data['players'][opponent_index]:
            # Show only the count of cards in opponent's hand, but keep the image field
            filtered_data['players'][opponent_index]['hand'] = [
                {'face_down': True, 'image': card.get('image', '')} 
                for card in filtered_data['players'][opponent_index]['hand']
            ]
    
    # Ensure image field is present in play area cards
    if 'play_area' in filtered_data:
        for card in filtered_data['play_area']:
            if 'owner' in card and card['owner'] == opponent_number and card.get('face_down', False):
                card['hidden'] = True
            # Ensure image field exists
            if 'image' not in card:
                card['image'] = ''
    
    return filtered_data

def generate_room_key(length=8):
    """Generate a unique room key."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_token(length=32):
    """Generate a secure token."""
    return secrets.token_hex(length)

@app.route('/create', methods=['GET'])
@app.route('/create_room', methods=['GET'])
def create_room():
    """Create a new room with a unique key and token."""
    try:
        # Generate unique room credentials
        room_key = generate_room_key()
        first_player_token = generate_token()
        
        # Initialize deck with cards from cards.py and shuffle
        deck = create_deck()
        random.shuffle(deck)
        
        # Create room data with initial game state
        room_data = {
            'players': [
                {
                    'hand': [],
                    'field': [],
                    'score': 0,
                    'token': first_player_token
                },
                {
                    'hand': [],
                    'field': [],
                    'score': 0,
                    'token': None  # Will be set when second player joins
                }
            ],
            'deck': deck,
            'discard_pile': [],
            'current_turn': 1,  # 1 for first player, 2 for second player
            'game_state': 'player_action',  # 'player_action' or 'player_discard'
            'pending_discard': []  # Store selected cards for discarding
        }
        
        # Store room in Firestore
        db.collection('rooms').document(room_key).set(room_data)
        
        return jsonify({
            'room_key': room_key,
            'first_player_token': first_player_token
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

def deal_initial_cards(room_ref):
    """Deal initial cards to both players."""
    # Get fresh room data
    room_snapshot = room_ref.get()
    room_data = room_snapshot.to_dict()
    
    deck = room_data.get('deck', []).copy()
    players = room_data.get('players', [{'hand': []}, {'hand': []}]).copy()
    
    # Deal 5 cards to each player
    for _ in range(5):
        for i in range(2):
            if deck and i < len(players):
                if 'hand' not in players[i]:
                    players[i]['hand'] = []
                card = deck.pop()
                if isinstance(card, dict) and 'image' not in card:
                    card['image'] = ''
                players[i]['hand'].append(card)
    
    # Update only the necessary fields using set with merge
    update_data = {
        'players': players,
        'deck': deck
    }
    room_ref.set(update_data, merge=True)  # Use set with merge to preserve other fields

@app.route('/join/<room_key>')
@app.route('/join_room/<room_key>', methods=['GET'])
def join_room(room_key):
    """Join an existing room."""
    try:
        # Get room from Firestore
        room_ref = db.collection('rooms').document(room_key)
        room = room_ref.get()
        
        if not room.exists:
            return jsonify({
                'error': 'Room does not exist'
            }), 404
            
        # Get room data
        room_data = room.to_dict()
        
        # Check if second player already exists
        if len(room_data.get('players', [])) >= 2 and room_data['players'][1]['token'] is not None:
            return jsonify({
                'error': 'Room is already full'
            }), 400
            
        # Generate second player token
        second_player_token = generate_token()
        print(f"Generated second player token: {second_player_token}")
        
        try:
            # First, get the current room data
            room_snapshot = room_ref.get()
            room_data = room_snapshot.to_dict()
            players = room_data.get('players', []).copy()  # Create a copy to modify
            
            print(f"Current players before update: {players}")
            
            # Ensure we have at least one player (should always be true)
            if not players:
                raise ValueError("Room has no players")
            
            # Create or update the second player
            if len(players) < 2:
                # Add new second player
                players.append({
                    'hand': [],
                    'field': [],
                    'score': 0,
                    'token': second_player_token
                })
                print("Added new second player")
            else:
                # Update existing second player
                if 'token' in players[1] and players[1]['token']:
                    print(f"Replacing existing token: {players[1]['token']}")
                players[1].update({
                    'hand': players[1].get('hand', []),
                    'field': players[1].get('field', []),
                    'score': players[1].get('score', 0),
                    'token': second_player_token
                })
                print("Updated existing second player")
            
            # Update the document directly (not in a transaction for now)
            update_data = {'players': players}
            print(f"Updating with data: {update_data}")
            
            # Use set with merge=True to preserve other fields
            room_ref.set(update_data, merge=True)
            
            # Verify the update
            updated_room = room_ref.get()
            updated_players = updated_room.to_dict().get('players', [])
            print(f"Players after update: {updated_players}")
            
            if len(updated_players) > 1 and updated_players[1].get('token') != second_player_token:
                print("WARNING: Token mismatch after update!")
                # Try one more time with a fresh update
                updated_players[1]['token'] = second_player_token
                room_ref.update({'players': updated_players})
                
        except Exception as e:
            print(f"Error in join_room: {str(e)}")
            raise
        
        # Deal initial cards to both players
        deal_initial_cards(room_ref)
        
        return jsonify({
            'second_player_token': second_player_token
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/render_info', methods=['GET'])
def render_info():
    """Get the current game state for rendering."""
    try:
        # Get parameters from query string
        room_key = request.args.get('room_key')
        player_token = request.args.get('player_token')
                
        print(f"Received request with params - room_key: {room_key}, player_token: {player_token}")
        
        # Check for required parameters
        if not all([room_key, player_token]):
            return jsonify({'error': 'Missing required parameters (room_key, player_token)'}), 400
        
        # Get room data
        room_ref = db.collection('rooms').document(room_key)
        room = room_ref.get()
        
        if not room.exists:
            return jsonify({'error': 'Room not found'}), 404
            
        room_data = room.to_dict()
        
        # Find the player's index based on the token
        players = room_data.get('players', [])
        player_idx = None
        opponent_idx = None
        
        for i, player in enumerate(players):
            if player.get('token') == player_token:
                player_idx = i
                opponent_idx = 1 if i == 0 else 0
                break
                    
        if player_idx is None:
            return jsonify({'error': 'Invalid player token'}), 403
                
        # Get player and opponent data
        player_data = players[player_idx] if player_idx < len(players) else {}
        opponent_data = players[opponent_idx] if opponent_idx < len(players) else {}
        
        return jsonify({
            'player_field': player_data.get('field', []),
            'opponent_field': opponent_data.get('field', []),
            'player_hand': player_data.get('hand', []),
            'opponent_hand_count': len(opponent_data.get('hand', [])),
            'player_score': player_data.get('score', 0),
            'opponent_score': opponent_data.get('score', 0),
            'current_turn': room_data.get('current_turn'),
            'game_state': room_data.get('game_state', 'unknown'),
            'your_turn': room_data.get('current_turn') == player_idx + 1
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/player_action', methods=['GET'])
def player_action():
    """Handle player actions (playing a card)."""
    try:
        # Get parameters from query string
        room_key = request.args.get('room_key')
        player_token = request.args.get('player_token')
        action = request.args.get('action', 'play')
        card_index = request.args.get('card_index', -1, type=int)
        
        # Ensure card_index is an integer
        card_index = int(card_index) if card_index is not None else -1
        
        print(f"Received request with params - room_key: {room_key}, player_token: {player_token}, action: {action}, card_index: {card_index}")
        
        # Check for required parameters
        if not all([room_key, player_token, action]):
            return jsonify({'error': 'Missing required parameters (room_key, player_token, action)'}), 400
            
        # For play action, card_index is required
        if action == 'play':
            if card_index is None:
                return jsonify({'error': 'Missing card_index for play action'}), 400
                
            try:
                card_index = int(card_index)
                # Allow -1 as a valid value for passing the turn
                if card_index < -1:
                    return jsonify({'error': 'Invalid card index'}), 400
            except ValueError:
                return jsonify({'error': 'card_index must be an integer'}), 400
        
        # Get room data
        room_ref = db.collection('rooms').document(room_key)
        room = room_ref.get()
        
        if not room.exists:
            return jsonify({'error': 'Room not found'}), 404
            
        room_data = room.to_dict()
        
        player, error_response, status_code = verify_player_turn(room_data, player_token)
        if error_response:
            return jsonify(error_response), status_code
            
        # Check for win condition at the start of turn
        player_score = room_data.get(f'player_{player}_score', 0)
        if player_score >= 7:
            return jsonify({
                'game_over': True,
                'winner': player,
                'message': f'Player {player} wins with {player_score} points!',
                'scores': {
                    'player_1': players[0].get('score', 0),
                    'player_2': players[1].get('score', 0)
                }
            }), 200
        
        # Get player data
        players = room_data.get('players', [])
        if player < 1 or player > len(players):
            return jsonify({'error': 'Invalid player number'}), 400
            
        player_data = players[player - 1]
        
        # Create copies to work with
        player_hand = player_data.get('hand', []).copy()
        player_field = player_data.get('field', []).copy()
        
        # Handle play action
        if action == 'play':
            # Handle pass turn (card_index = -1)
            if card_index == -1:
                # Check if player has 5 or 6 cards
                if len(player_hand) in [5, 6]:
                    cards_to_discard = len(player_hand) - 4
                    # Update the game state in the database
                    room_ref.set({
                        'game_state': 'player_discard'
                    }, merge=True)
                    # Get the updated room data
                    room_data = room_ref.get().to_dict()
                    return jsonify({
                        'success': False,
                        'message': f'Discard {cards_to_discard} card(s) down to 4',
                        'needs_discard': True,
                        'hand_size': len(player_hand),
                        'cards_to_discard': cards_to_discard,
                        'current_game_state': room_data.get('game_state', 'unknown')
                    })
                # If not, just switch turns
                room_ref.update({
                    'current_turn': 2 if room_data['current_turn'] == 1 else 1,
                    'game_state': 'player_action'
                })
                return jsonify({
                    'success': True,
                    'message': 'Turn passed',
                    'player_num': player
                })
            
            # Handle playing a card
            if card_index < 0 or card_index >= len(player_hand):
                return jsonify({'error': 'Invalid card selection'}), 400
            
            # Get the selected card and ensure it has an image field
            card = player_hand.pop(card_index)
            if 'image' not in card:
                card['image'] = ''
            
            # Add to field
            if 'field' not in player_data:
                player_data['field'] = []
            player_data['field'].append(card)
            
            # Update player data
            players[player - 1] = player_data
            
            # Prepare updates
            updates = {
                'players': players,
                'current_turn': 2 if player == 1 else 1,  # Switch turns
                'game_state': 'player_action'
            }
            
            room_ref.update(updates)
            
            return jsonify({
                'success': True,
                'card_played': card,
                'player_num': player,
                'updated_hand': player_hand
            })
        # Handle draw cards if action is draw
        elif action == 'draw' and card_index == -1:
            # Get the current deck and discard pile
            deck = room_data.get('deck', []).copy()
            discard_pile = room_data.get('discard_pile', [])
            
            # Draw up to 2 cards if available
            drawn_cards = []
            for _ in range(2):
                if deck:
                    card = deck.pop()
                    if 'image' not in card:
                        card['image'] = ''
                    drawn_cards.append(card)
                # If deck is empty but there are cards in discard pile, shuffle them into the deck
                elif not deck and discard_pile:
                    deck = [card for card in discard_pile if isinstance(card, dict)]
                    random.shuffle(deck)
                    discard_pile = []
                    if deck:  # If we managed to refill the deck
                        card = deck.pop()
                        if 'image' not in card:
                            card['image'] = ''
                        drawn_cards.append(card)
            
            # Update player's hand with drawn cards
            player_hand.extend(drawn_cards)
            
            # If player has more than 4 cards, automatically discard excess
            if len(player_hand) > 4:
                # Calculate how many cards to discard
                excess = len(player_hand) - 4
                discarded = player_hand[-excess:]  # Take from the end (newest cards)
                player_hand = player_hand[:-excess]  # Keep the rest
                # Add discarded cards to bottom of deck
                deck = discarded + deck
                message = f'Drew {len(drawn_cards)} card(s) and discarded {len(discarded)} excess card(s)'
            else:
                message = f'Drew {len(drawn_cards)} card(s)' if drawn_cards else 'No cards to draw'
            
            # Update player's hand and game state
            players[player - 1]['hand'] = player_hand
            updates = {
                'players': players,
                'deck': deck,
                'discard_pile': discard_pile,
                'current_turn': 2 if player == 1 else 1,  # Switch turns
                'game_state': 'player_action'
            }
        
        room_ref.update(updates)
        
        response = {
            'success': True,
            'updated_hand': player_hand,
            'updated_field': player_field,
            'card_effect': 'draw_1' if card.get('value') == 2 and drawn_card is not None else None,
            'drawn_card': drawn_card if card.get('value') == 2 and drawn_card is not None else None
        }
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/discard_cards', methods=['GET'])
def discard_cards():
    """Discard selected cards from hand to the bottom of the deck."""
    try:
        # Get parameters from query string
        room_id = request.args.get('room_id') or request.args.get('room_key')
        player_token = request.args.get('player_token')
        card_indices_str = request.args.get('card_indices', '')
        
        # Convert card_indices from string to list of integers (max 2 cards)
        card_indices = [int(idx.strip()) for idx in card_indices_str.split(',') if idx.strip().isdigit()]
        
        # Validate parameters
        if not all([room_id, player_token]):
            return jsonify({'error': 'Missing required parameters'}), 400
            
        # Get room data to check current hand size
        room_ref = db.collection('rooms').document(room_id)
        room = room_ref.get()
        
        if not room.exists:
            return jsonify({'error': 'Room not found'}), 404
            
        room_data = room.to_dict()
        
        # Get current player's hand size
        player, error_response, status_code = verify_player_turn(room_data, player_token, 'player_discard')
        if error_response:
            return jsonify(error_response), status_code
            
        players = room_data.get('players', [])
        if player < 1 or player > len(players):
            return jsonify({'error': 'Invalid player number'}), 400
            
        player_hand = players[player - 1].get('hand', [])
        hand_size = len(player_hand)
        
        # Determine required discards based on hand size
        required_discards = 1 if hand_size == 5 else 2 if hand_size == 6 else 0
        
        if required_discards == 0:
            return jsonify({'error': 'No discards needed'}), 400
            
        # Validate number of cards being discarded
        if len(card_indices) != required_discards:
            return jsonify({'error': f'You must discard exactly {required_discards} card(s)'}), 400
            
        # Get player data and deck
        player_data = players[player - 1]
        player_hand = players[player - 1].get('hand', []).copy()
        deck = room_data.get('deck', []).copy()
        discard_pile = room_data.get('discard_pile', [])
        
        # Validate card indices
        if not all(isinstance(idx, int) and 0 <= idx < len(player_hand) for idx in card_indices):
            return jsonify({'error': 'One or more invalid card indices'}), 400
            
        # Remove cards from hand (in reverse order to maintain indices)
        discarded_cards = []
        for idx in sorted(card_indices, reverse=True):
            discarded_cards.append(player_hand.pop(idx))
        
        # Add discarded cards to bottom of deck
        deck = discarded_cards + deck
        
        # Draw 2 cards
        drawn_cards = []
        for _ in range(2):
            if deck:
                drawn_cards.append(deck.pop())
            elif discard_pile:  # If deck is empty but there are cards in discard pile
                # Reshuffle discard pile into deck
                deck = discard_pile.copy()
                import random
                random.shuffle(deck)
                discard_pile = []
                if deck:  # If we managed to refill the deck
                    drawn_cards.append(deck.pop())
        
        # Add drawn cards to player's hand
        player_hand.extend(drawn_cards)
        players[player - 1]['hand'] = player_hand
        
        # Switch turns
        new_turn = 2 if room_data.get('current_turn') == 1 else 1
        
        # Update the room with the new state
        updates = {
            'players': players,
            'deck': deck,
            'discard_pile': discard_pile,
            'game_state': 'player_action',
            'current_turn': new_turn  # Switch turns
        }
        room_ref.set(updates, merge=True)
        
        # Return success response
        return jsonify({
            'success': True,
            'message': f'Discarded {len(discarded_cards)} and drew {len(drawn_cards)} card(s). Turn ended.',
            'drawn_cards': len(drawn_cards),
            'new_hand_size': len(player_hand),
            'new_deck_size': len(deck),
            'turn_ended': True,
            'next_player': new_turn
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/scores/<room_id>', methods=['GET'])
@app.route('/scores/<room_id>', methods=['GET'])
def get_scores(room_id):
    """Get current scores for both players."""
    try:
        # Get room data
        room_ref = db.collection('rooms').document(room_id)
        room = room_ref.get()
        
        if not room.exists:
            return jsonify({'error': 'Room not found'}), 404
            
        room_data = room.to_dict()
        players = room_data.get('players', [])
        
        return jsonify({
            'success': True,
            'scores': {
                'player_1': players[0].get('score', 0) if len(players) > 0 else 0,
                'player_2': players[1].get('score', 0) if len(players) > 1 else 0
            },
            'game_state': room_data.get('game_state')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def test_filter_game_data():
    """Test the filter_game_data_for_player function with sample game data."""
    # Sample game data
    sample_game = {
        'game_id': 'test123',
        'current_turn': 1,
        'game_state': 'playing',
        'players': [
            {
                'id': 'player1',
                'token': 'token1',
                'name': 'Alice',
                'hand': [
                    {'id': 'card1', 'name': 'Wolf', 'attack': 3, 'health': 5},
                    {'id': 'card2', 'name': 'Rabbit', 'attack': 1, 'health': 2}
                ],
                'health': 30
            },
            {
                'id': 'player2',
                'token': 'token2',
                'name': 'Bob',
                'hand': [
                    {'id': 'card3', 'name': 'Bear', 'attack': 4, 'health': 6},
                    {'id': 'card4', 'name': 'Fox', 'attack': 2, 'health': 3},
                    {'id': 'card5', 'name': 'Deer', 'attack': 2, 'health': 4}
                ],
                'health': 30
            }
        ],
        'play_area': [
            {'id': 'card6', 'name': 'Owl', 'attack': 2, 'health': 3, 'owner': 1, 'face_down': False},
            {'id': 'card7', 'name': 'Eagle', 'attack': 3, 'health': 2, 'owner': 2, 'face_down': True}
        ]
    }
    
    print("=== Testing filter_game_data_for_player ===\n")
    
    # Test for player 1
    print("--- Player 1's view ---")
    filtered_p1 = filter_game_data_for_player(sample_game, 1)
    print("Player 1's hand:", filtered_p1['players'][0]['hand'])  # Should show actual cards
    print("Player 2's hand:", filtered_p1['players'][1]['hand'])  # Should show face-down cards
    print("Play area:", filtered_p1['play_area'])  # Should show face-up cards and hide face-down opponent cards
    
    # Test for player 2
    print("\n--- Player 2's view ---")
    filtered_p2 = filter_game_data_for_player(sample_game, 2)
    print("Player 1's hand:", filtered_p2['players'][0]['hand'])  # Should show face-down cards
    print("Player 2's hand:", filtered_p2['players'][1]['hand'])  # Should show actual cards
    print("Play area:", filtered_p2['play_area'])  # Should show face-up cards and hide face-down opponent cards

if __name__ == '__main__':
    # Run the test function
    test_filter_game_data()
    # Start the Flask app
    app.run(debug=True, port=5000)
