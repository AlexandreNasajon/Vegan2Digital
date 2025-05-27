// Função para criar um jogo
async function createGame(userId) {
    const response = await fetch("/api/create_game", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId })
    });
    return await response.json();
}

// Função para carregar um jogo existente
async function loadGame(gameId) {
    const response = await fetch(`/api/game/${gameId}`);
    return await response.json();
}

// Exemplo: Após login no Supabase
async function onLogin(user) {
    const game = await createGame(user.id);
    renderGame(game.game_state);
}