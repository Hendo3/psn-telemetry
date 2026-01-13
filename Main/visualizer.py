import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# --- CONFIGURAÇÃO ---
BASE_DIR = Path(__file__).parent.resolve()

# Estilo Dark/Cyberpunk simplificado
plt.style.use('dark_background')
sns.set_palette("bright")

def find_dump_file():
	"""Procura automaticamente pelo primeiro arquivo de dump JSON na pasta."""
	json_files = list(BASE_DIR.glob("psn_full_dump_*.json"))
	
	if not json_files:
		print("--> [ERRO] Nenhum arquivo 'psn_full_dump_*.json' encontrado.")
		print("--> Execute o 'psn_games_extractor.py' primeiro.")
		sys.exit(1)
		
	# Pega o arquivo mais recente se houver vários
	latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
	print(f"--> Arquivo de dados encontrado: {latest_file.name}")
	return latest_file

def load_data(filepath):
	with open(filepath, 'r', encoding='utf-8') as f:
		data = json.load(f)
	
	# Extrair nome de usuário dos metadados para nomear o arquivo depois
	username = data.get('metadata', {}).get('user', 'unknown_user')
	
	df = pd.json_normalize(data['full_library'])
	df.columns = [c.replace('playtime.', '').replace('trophies.', '').replace('breakdown.', '') for c in df.columns]
	
	# Tratamento Numérico
	df['hours'] = pd.to_numeric(df['hours'], errors='coerce').fillna(0.0)
	df['progress'] = df['progress'].astype(str).str.replace('%', '')
	df['progress'] = pd.to_numeric(df['progress'], errors='coerce').fillna(0.0)
	
	# Remove jogos zerados/bugados (< 0.5h)
	df_clean = df[df['hours'] > 0.5].copy()
	
	return df_clean, username

def categorize_game(row):
	h = row['hours']
	if h < 5: return "1. Teste (< 5h)"
	if h < 20: return "2. Curto (5-20h)"
	if h < 50: return "3. Médio (20-50h)"
	if h < 100: return "4. Dedicado (50-100h)"
	return "5. Vício (> 100h)"

def get_status(row):
	if row['is_platinum_earned']: return "Platina"
	if row['progress'] == 100: return "100% (S/ Plat)"
	if row['progress'] < 10: return "Drop/Início"
	return "Jogando / Zerado"

def generate_static_image(df, username):
	# Preparar Dados
	df['Categoria'] = df.apply(categorize_game, axis=1)
	df['Status'] = df.apply(get_status, axis=1)
	
	# Criar Figura (Canvas)
	fig = plt.figure(figsize=(20, 12))
	fig.patch.set_facecolor('#121212') # Fundo quase preto
	
	# Grid: 2 linhas, 2 colunas.
	gs = fig.add_gridspec(2, 2)
	
	# --- GRÁFICO 1: TOP 15 (Barra Horizontal) ---
	ax1 = fig.add_subplot(gs[:, 0]) # Ocupa toda a esquerda
	top15 = df.sort_values('hours', ascending=False).head(15)
	
	# CORREÇÃO 1: Adicionado hue='title' e legend=False para calar o FutureWarning
	sns.barplot(data=top15, x='hours', y='title', hue='title', ax=ax1, palette='viridis', legend=False)
	
	ax1.set_title('TOP 15 MAIS JOGADOS (Horas)', fontsize=16, color='white', pad=20)
	ax1.set_xlabel('')
	ax1.set_ylabel('')
	ax1.bar_label(ax1.containers[0], fmt='%.0fh', padding=3, color='white')
	
	# --- GRÁFICO 2: DISTRIBUIÇÃO (Histograma Categorizado) ---
	ax2 = fig.add_subplot(gs[0, 1]) # Canto superior direito
	
	dist_data = df['Categoria'].value_counts().sort_index()
	
	# CORREÇÃO 2: Adicionado hue=dist_data.index e legend=False
	sns.barplot(x=dist_data.index, y=dist_data.values, hue=dist_data.index, ax=ax2, palette='magma', legend=False)
	
	ax2.set_title('DISTRIBUIÇÃO DA BIBLIOTECA (Qtd Jogos)', fontsize=16, color='white', pad=20)
	ax2.set_ylabel('')
	
	# CORREÇÃO 3: Substituído set_xticklabels por tick_params para evitar UserWarning
	ax2.tick_params(axis='x', rotation=15)
	
	ax2.bar_label(ax2.containers[0], color='white')

	# --- GRÁFICO 3: STATUS (Pizza/Donut) ---
	ax3 = fig.add_subplot(gs[1, 1]) # Canto inferior direito
	
	status_counts = df['Status'].value_counts()
	
	color_dict = {
		'Jogando / Zerado': '#ff0055', 
		'Drop/Início': '#444444', 
		'Platina': '#00ffff', 
		'100% (S/ Plat)': '#00ff00'
	}
	pie_colors = [color_dict.get(l, '#aaaaaa') for l in status_counts.index]

	wedges, texts, autotexts = ax3.pie(
		status_counts, 
		labels=status_counts.index, 
		autopct='%1.1f%%', 
		startangle=90, 
		colors=pie_colors,
		textprops=dict(color="white"),
		wedgeprops=dict(width=0.4)
	)
	ax3.set_title('COMPOSIÇÃO DA CONTA', fontsize=16, color='white', pad=20)
	plt.setp(autotexts, size=10, weight="bold")

	# Ajustes Finais
	plt.tight_layout(pad=3.0)
	
	# Salvar
	output = BASE_DIR / f'{username}.png'
	plt.savefig(output, dpi=150, facecolor='#121212')
	print(f"--> IMAGEM GERADA: {output}")

if __name__ == "__main__":
	json_file = find_dump_file()
	df, username = load_data(json_file)
	generate_static_image(df, username)