import firebase_admin
from firebase_admin import credentials, firestore
from collections import defaultdict

# Card configuration with base image names (without numbers)
CARDS = {
    # Aquatic cards
    'fast_tuna': {'value': 1, 'type': 'aquatic', 'base_image': 'tuna'},
    'yellow_seahorse': {'value': 1, 'type': 'aquatic', 'base_image': 'seahorse'},
    'sea_turtle': {'value': 2, 'type': 'aquatic', 'base_image': 'turtle'},
    'elusive_jellyfish': {'value': 2, 'type': 'aquatic', 'base_image': 'jellyfish'},
    'happy_dolphin': {'value': 3, 'type': 'aquatic', 'base_image': 'dolphin'},
    'shy_stingray': {'value': 3, 'type': 'aquatic', 'base_image': 'stingray'},
    'swift_swordfish': {'value': 3, 'type': 'aquatic', 'base_image': 'swordfish'},
    'shark': {'value': 4, 'type': 'aquatic', 'base_image': 'shark'},
    # Terrestrial cards
    'tiny_mouse': {'value': 1, 'type': 'terrestrial', 'base_image': 'mouse'},
    'quick_squirrel': {'value': 1, 'type': 'terrestrial', 'base_image': 'squirrel'},
    'mountain_goat': {'value': 2, 'type': 'terrestrial', 'base_image': 'goat'},
    'sly_fox': {'value': 2, 'type': 'terrestrial', 'base_image': 'fox'},
    'graceful_stag': {'value': 3, 'type': 'terrestrial', 'base_image': 'stag'},
    'savannah_zebra': {'value': 3, 'type': 'terrestrial', 'base_image': 'zebra'},
    'fierce_wolf': {'value': 3, 'type': 'terrestrial', 'base_image': 'wolf'},
    'regal_lion': {'value': 4, 'type': 'terrestrial', 'base_image': 'lion'},
    # Amphibian cards
    'pond_frog': {'value': 1, 'type': 'amphibian', 'base_image': 'frog'},
    'red_crab': {'value': 2, 'type': 'amphibian', 'base_image': 'crab'},
    'river_otter': {'value': 3, 'type': 'amphibian', 'base_image': 'otter'},
    'swamp_crocodile': {'value': 4, 'type': 'amphibian', 'base_image': 'crocodile'}
}

# Impact cards (event cards that affect gameplay)
IMPACT_CARDS = {
    'competition': {'base_image': 'competition'},
    'confusion': {'base_image': 'confusion'},
    'domesticate': {'base_image': 'domesticate'},
    'earthquake': {'base_image': 'earthquake'},
    'flood': {'base_image': 'flood'},
    'prey': {'base_image': 'prey'},
    'scare': {'base_image': 'scare'},
    'trap': {'base_image': 'trap'},
    'virus': {'base_image': 'virus'},
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
            
        base_image = card_data['base_image']
        
        # For each copy of the card, assign the next available image variation
        for _ in range(quantity):
            variation_counters[card_name] += 1
            variation = variation_counters[card_name]
            
            # Create the image path based on the card name and variation
            if card_name == 'fast_tuna':
                image_path = f'cards/tuna{variation}.png'  # tuna1, tuna2, tuna3
            elif card_name == 'yellow_seahorse':
                image_path = f'cards/seahorse{variation}.png'  # seahorse1, seahorse2, seahorse3
            elif card_name == 'sea_turtle':
                image_path = f'cards/turtle{min(variation, 2)}.png'  # turtle1, turtle2
            elif card_name == 'elusive_jellyfish':
                image_path = f'cards/jellyfish{min(variation, 2)}.png'  # jellyfish1, jellyfish2
            elif card_name == 'tiny_mouse':
                image_path = f'cards/mouse{variation}.png'  # mouse1, mouse2, mouse3
            elif card_name == 'quick_squirrel':
                image_path = f'cards/squirrel{variation}.png'  # squirrel1, squirrel2, squirrel3
            elif card_name == 'mountain_goat':
                image_path = f'cards/goat{min(variation, 2)}.png'  # goat1, goat2
            elif card_name == 'sly_fox':
                image_path = f'cards/fox{min(variation, 2)}.png'  # fox1, fox2
            elif card_name == 'pond_frog':
                image_path = f'cards/frog{variation}.png'  # frog1, frog2, frog3
            elif card_name == 'red_crab':
                image_path = f'cards/crab{min(variation, 2)}.png'  # crab1, crab2
            else:
                # For cards without variations, use the base image
                image_path = f'cards/{base_image}.png'
            
            # Add the card to the deck
            deck.append({
                'name': card_name,
                'image': image_path,
                **{k: v for k, v in card_data.items() if k != 'base_image'}
            })
    
    # Then handle impact cards (1 of each)
    for card_name, card_data in IMPACT_CARDS.items():
        for _ in range(1):  #  of each impact card
            deck.append({
                'name': card_name,
                'image': f'cards/{card_data["base_image"]}.png',
                'type': 'impact'
            })
    
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