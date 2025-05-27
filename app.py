import os
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
import os
from dotenv import load_dotenv

app = Flask(__name__, static_folder='static', static_url_path='')

# Configurações do Flask
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Please set SUPABASE_URL and SUPABASE_KEY in .env file")

# Initialize the Supabase client
client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Rota principal
@app.route("/")
def home():
    return render_template("index.html")

# API para criar um jogo
@app.route("/api/create_game", methods=["POST"])
def create_game():
    user_id = request.json.get("user_id")
    game_state = {"deck": shuffle_deck(), "players": {}}
    
    # Insere no Supabase
    response = client.table("games").insert({
        "player1": user_id,
        "game_state": game_state
    }).execute()
    
    return jsonify(response.data)

# API para buscar um jogo
@app.route("/api/game/<game_id>")
def get_game(game_id):
    response = client.table("games").select("*").eq("id", game_id).execute()
    return jsonify(response.data)

# Função auxiliar: embaralhar cartas
def shuffle_deck():
    suits = ['♥', '♦', '♣', '♠']
    values = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    deck = [{"suit": s, "value": v} for s in suits for v in values]
    import random
    random.shuffle(deck)
    return deck

# Esta parte garante que o app só será executado quando rodado diretamente
# e não quando importado como um módulo
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)