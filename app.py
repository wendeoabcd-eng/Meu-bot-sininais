import os
import time
import threading
import requests
import telebot
import google.generativeai as genai
from flask import Flask

# --- MINI SERVIDOR PARA MANTER O BOT VIVO ---
# Isso impede que o Render/Hugging Face desligue o bot por inatividade
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot de Sinais Online ✅", 200

# --- CONFIGURAÇÕES DE AMBIENTE ---
# As chaves abaixo devem ser configuradas no painel do servidor (Secrets/Environment Variables)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ODDS_API_KEY = os.environ.get('ODDS_API_KEY')
CHAT_ID = os.environ.get('CHAT_ID')

# Inicialização das APIs
bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def analise_ia_gemini(time_fav, zebra, odd):
    """Solicita uma análise estatística ao Gemini 1.5"""
    prompt = (
        f"Aja como um especialista em trading esportivo. "
        f"Analise o jogo: {time_fav} vs {zebra}. "
        f"Entrada: Vitória do {time_fav}. Odd atual: {odd}. "
        f"Se a probabilidade de vitória for superior a 70%, responda apenas começando com 'APROVADO' "
        f"seguido de uma justificativa curta de no máximo 10 palavras. "
        f"Caso contrário, responda 'REPROVADO'."
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"ERRO NA ANALISE: {e}"

def buscar_e_processar_sinais():
    """Busca odds na API e filtra as melhores oportunidades"""
    # Exemplo: Buscando jogos de futebol
    url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'eu',
        'markets': 'h2h',
        'oddsFormat': 'decimal'
    }
    
    try:
        res = requests.get(url, params=params)
        jogos = res.json()
        
        for jogo in jogos:
            if not jogo.get('bookmakers'): continue
            
            home_team = jogo['home_team']
            away_team = jogo['away_team']
            odds_list = jogo['bookmakers'][0]['markets'][0]['outcomes']

            for o in odds_list:
                # FILTRO: Odds entre 1.50 e 1.80 (Favoritos com valor)
                if 1.50 <= o['price'] <= 1.80:
                    favorito = o['name']
                    adversario = away_team if favorito == home_team else home_team
                    
                    # Validação com a IA Gemini
                    print(f"Analisando: {favorito}...")
                    veredito = analise_ia_gemini(favorito, adversario, o['price'])

                    if "APROVADO" in veredito.upper():
                        enviar_sinal_telegram(favorito, adversario, o['price'], veredito)
                        time.sleep(10) # Evita envio em massa
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")

def enviar_sinal_telegram(time_fav, zebra, odd, analise):
    """Formata e envia a mensagem para o Telegram"""
    texto_analise = analise.replace("APROVADO", "").strip()
    mensagem = (
        f"🎯 **SINAL DE ALTA PROBABILIDADE**\n\n"
        f"⚽ **Jogo:** {time_fav} vs {zebra}\n"
        f"🔥 **Entrada:** Vitória {time_fav}\n"
        f"📈 **Odd:** {odd}\n\n"
        f"🧠 **Análise Gemini:**\n_{texto_analise}_"
    )
    try:
        bot.send_message(CHAT_ID, mensagem, parse_mode="Markdown")
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

# --- LOOP DE EXECUÇÃO EM SEGUNDO PLANO ---
def main_loop():
    print("🤖 Bot de Sinais iniciado!")
    while True:
        buscar_e_processar_sinais()
        # Espera 1 hora antes de checar novamente para não gastar sua cota de API
        time.sleep(3600)

if __name__ == "__main__":
    # Inicia o loop do bot em uma linha separada para não travar o servidor web
    threading.Thread(target=main_loop, daemon=True).start()
    
    # Inicia o servidor Flask na porta exigida pelo serviço de hospedagem
    port = int(
