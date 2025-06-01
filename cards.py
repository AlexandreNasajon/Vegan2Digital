import firebase_admin
from firebase_admin import credentials, firestore
from collections import defaultdict

# Card configuration with base image names (without numbers)
CARDS = {
    # Aquatic cards
    'fast_tuna': {'value': 1, 'type': 'aquatic', 'image': 'tuna1'},
    'yellow_seahorse': {'value': 1, 'type': 'aquatic', 'image': 'seahorse1'},
    'sea_turtle': {'value': 2, 'type': 'aquatic', 'image': 'turtle1'},
    'elusive_jellyfish': {'value': 2, 'type': 'aquatic', 'image': 'jellyfish1'},
    'happy_dolphin': {'value': 3, 'type': 'aquatic', 'image': 'dolphin1'},
    'shy_stingray': {'value': 3, 'type': 'aquatic', 'image': 'stingray'},
    'swift_swordfish': {'value': 3, 'type': 'aquatic', 'image': 'swordfish'},
    'shark': {'value': 4, 'type': 'aquatic', 'image': 'shark'},
    # Terrestrial cards
    'tiny_mouse': {'value': 1, 'type': 'terrestrial', 'image': 'mouse1'},
    'quick_squirrel': {'value': 1, 'type': 'terrestrial', 'image': 'squirrel1'},
    'mountain_goat': {'value': 2, 'type': 'terrestrial', 'image': 'goat1'},
    'sly_fox': {'value': 2, 'type': 'terrestrial', 'image': 'fox1'},
    'graceful_stag': {'value': 3, 'type': 'terrestrial', 'image': 'stag'},
    'savannah_zebra': {'value': 3, 'type': 'terrestrial', 'image': 'zebra'},
    'fierce_wolf': {'value': 3, 'type': 'terrestrial', 'image': 'wolf'},
    'regal_lion': {'value': 4, 'type': 'terrestrial', 'image': 'lion'},
    # Amphibian cards
    'pond_frog': {'value': 1, 'type': 'amphibian', 'image': 'frog1'},
    'red_crab': {'value': 2, 'type': 'amphibian', 'image': 'crab1'},
    'river_otter': {'value': 3, 'type': 'amphibian', 'image': 'otter'},
    'swamp_crocodile': {'value': 4, 'type': 'amphibian', 'image': 'crocodile'}
}

# Impact cards (event cards that affect gameplay)
IMPACT_CARDS = {
    'competition': {'image': 'competition'},
    'confusion': {'image': 'confusion'},
    'domesticate': {'image': 'domesticate'},
    'earthquake': {'image': 'earthquake'},
    'flood': {'image': 'flood'},
    'prey': {'image': 'prey'},
    'scare': {'image': 'scare'},
    'trap': {'image': 'trap'},
    'virus': {'image': 'virus'},
}

# Deck composition: card_name: quantity
DECK_COMPOSITION = {
    # Impact cards
    'competition': 1,
    'confusion': 1,
    'domesticate': 1,
    'earthquake': 1,
    'flood': 1,
    'prey': 1,
    'scare': 1,
    'trap': 1,
    'virus': 1,
    'fisher': 3,
    'hunter': 3,
    # Aquatic cards
    'fast_tuna': 3,
    'yellow_seahorse': 3,
    'sea_turtle': 2,
    'elusive_jellyfish': 2,
    'shy_stingray': 1,
    'swift_swordfish': 1,
    'happy_dolphin': 1,
    'shark': 1,
    # Terrestrial cards
    'tiny_mouse': 3,
    'quick_squirrel': 3,
    'sly_fox': 2,
    'mountain_goat': 2,
    'graceful_stag': 1,
    'fierce_wolf': 1,
    'savannah_zebra': 1,    
    'regal_lion': 1,
    # Amphibian cards
    'pond_frog': 3,
    'red_crab': 2,
    'river_otter': 1,
    'swamp_crocodile': 1
}

def create_deck():  
    """Create a deck with unique card instances, each with its own image variation."""
    deck = []
    
    # Track which image variation to use for each card type
    variation_counters = defaultdict(int)
    
    # First, handle regular animal cards
    for card_name, quantity in DECK_COMPOSITION.items():
        if card_name in IMPACT_CARDS:
            continue  # Skip impact cards for now
            
        card_data = CARDS.get(card_name)
        if not card_data:
            continue
            
        # For each copy of the card, create a copy of the card data
        for _ in range(quantity):
            # Create a deep copy of the card data to avoid modifying the original
            card_copy = card_data.copy()
            
            # If the card has an image field, use it directly
            if 'image' in card_copy:
                card_copy['image'] = f"cards/{card_copy['image']}.png"
            
            # Add the card to the deck with its name
            card_copy['name'] = card_name
            deck.append(card_copy)
    
    # Then handle impact cards (1 of each)
    for card_name, card_data in IMPACT_CARDS.items():
        card_copy = card_data.copy()
        card_copy['name'] = card_name
        card_copy['type'] = 'impact'
        card_copy['effect'] = card_name
        if 'image' in card_copy:
            card_copy['image'] = f'cards/{card_copy["image"]}.png'
        deck.append(card_copy)
    return deck

def initialize_cards():
    """Initialize or update the cards in Firestore."""
    try:
        # Initialize Firebase Admin SDK
        cred = credentials.Certificate('vegan-cardgame-firebase-adminsdk-fbsvc-b2013bb175.json')
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Reference to the cards collection
        cards_ref = db.collection('cards')
        
        # Clear existing cards
        docs = cards_ref.stream()
        for doc in docs:
            doc.reference.delete()
        
        # Create a deck with unique card instances
        deck = create_deck()
        
        # Add each card to the collection
        for i, card in enumerate(deck, 1):
            doc_ref = cards_ref.document(f"{card['name']}_{i}")
            doc_ref.set({
                'name': card['name'],
                'image': card['image'],
                **{k: v for k, v in card.items() if k not in ['name', 'image']}
            })
            print(f"Added card: {card['name']} ({card['image']})")
        
        print(f"\nSuccessfully added {len(deck)} cards to the Firestore 'cards' collection.")
        return True
        
    except Exception as e:
        print(f"\nError initializing cards: {str(e)}")
        return False
    finally:
        # Clean up Firebase app to avoid issues with multiple initializations
        try:
            firebase_admin.delete_app(firebase_admin.get_app())
        except:
            pass

if __name__ == '__main__':
    print("Initializing cards in Firestore...\n")
    if initialize_cards():
        print("\nCard initialization completed successfully!")
    else:
        print("\nCard initialization failed. Please check the error messages above.")