import tkinter as tk
from tkinter import ttk, messagebox
from serpapi import GoogleSearch
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import threading
import sys 
import os
import urllib3


def resource_path(relative_path):
    """Retorna o caminho absoluto, mesmo dentro do .exe"""
    try:
        base_path = sys._MEIPASS  # usado quando empacotado
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# 🔑 SUA CHAVE SERPAPI AQUI
API_KEY = "SUA_API_KEY_AQUI"

# Desativa alertas SSL de sites com certificados problemáticos
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Dicionário de cidades e bairros
locais = {
    "São Paulo": ["Moema", "Pinheiros", "Tatuapé", "Santana", "Morumbi"],
    "Rio de Janeiro": ["Copacabana", "Barra da Tijuca", "Botafogo", "Tijuca", "Ipanema"],
    "Curitiba": ["Centro", "Água Verde", "Batel"],
    "Belo Horizonte": ["Savassi", "Funcionários", "Buritis"]
}

# Caminho do arquivo Excel geral (onde ficam todos os resultados)
ARQUIVO_GERAL = "condominios_coletados.xlsx"

# Lê dados já coletados (para evitar repetição)
def carregar_existentes():
    if os.path.exists(ARQUIVO_GERAL):
        df = pd.read_excel(ARQUIVO_GERAL)
        return set(df["Site"].tolist())
    return set()

# Salva novos resultados sem duplicar
def salvar_dados_novos(dados):
    novos_df = pd.DataFrame(dados)
    if os.path.exists(ARQUIVO_GERAL):
        antigo_df = pd.read_excel(ARQUIVO_GERAL)
        combinado_df = pd.concat([antigo_df, novos_df], ignore_index=True).drop_duplicates(subset=["Site"])
        combinado_df.to_excel(ARQUIVO_GERAL, index=False)
    else:
        novos_df.to_excel(ARQUIVO_GERAL, index=False)

# --- LÓGICA DE BUSCA (executada em thread separada) ---
def worker_busca(cidade, bairro, on_done_callback, on_progress_callback):
    dados = []
    sites_existentes = carregar_existentes()

    consultas = [
        f"lista de condomínios em {bairro}, {cidade}",
        f"condomínios residenciais em {bairro}, {cidade}",
        f"prédios e condomínios em {bairro}, {cidade}"
    ]

    todos_links = []

    # Coleta todos os links primeiro
    for consulta in consultas:
        for start in [0, 10, 20]:
            params = {
                "engine": "google",
                "q": consulta,
                "google_domain": "google.com.br",
                "hl": "pt-BR",
                "num": "10",
                "start": start,
                "api_key": API_KEY
            }
            try:
                search = GoogleSearch(params)
                results = search.get_dict()
                links = [r["link"] for r in results.get("organic_results", []) if "link" in r]
                todos_links.extend(links)
            except Exception as e:
                print(f"Erro ao buscar links: {e}")

    todos_links = list(set(todos_links))  # remove duplicados
    total_links = len(todos_links)
    print(f"Total de links para processar: {total_links}")

    for i, link in enumerate(todos_links, start=1):
        try:
            if link in sites_existentes:
                on_progress_callback(i, total_links)
                continue

            resposta = requests.get(link, timeout=10, verify=False)
            sopa = BeautifulSoup(resposta.text, "html.parser")
            texto = sopa.get_text().lower()

            if "condomínio" in texto or "condominio" in texto:
                nome = sopa.title.string.strip() if sopa.title else "Não informado"
                telefone = re.search(r"\(?\d{2}\)?\s?\d{4,5}-\d{4}", texto)
                email = re.search(r"[\w\.-]+@[\w\.-]+", texto)
                endereco = re.search(r"(rua|avenida|av\.|estrada|praça)\s[^\n]{10,60}", texto)

                dados.append({
                    "Cidade": cidade,
                    "Bairro": bairro,
                    "Site": link,
                    "Nome Condomínio": nome,
                    "Telefone": telefone.group(0) if telefone else "Não encontrado",
                    "Contato": email.group(0) if email else "Não encontrado",
                    "Endereço": endereco.group(0).capitalize() if endereco else "Não encontrado"
                })
            time.sleep(1)
        except Exception as e:
            print(f"Erro ao acessar {link}: {e}")
        finally:
            on_progress_callback(i, total_links)  # atualiza progresso visual

    on_done_callback(dados)


# --- CALLBACKS DA INTERFACE ---
def on_search_done(dados):
    progress.stop()
    btn_buscar.config(state="normal")

    if dados:
        salvar_dados_novos(dados)
        messagebox.showinfo("Concluído", f"✅ {len(dados)} novos condomínios adicionados!")
    else:
        messagebox.showinfo("Resultado", "⚠️ Nenhum novo condomínio encontrado.")

def buscar_condominios():
    cidade = combo_cidade.get()
    bairro = combo_bairro.get()
    if not cidade or not bairro:
        messagebox.showwarning("Aviso", "Selecione uma cidade e um bairro!")
        return

    btn_buscar.config(state="disabled")
    progress.start(10)

    thread = threading.Thread(
        target=worker_busca,
        args=(cidade, bairro, lambda dados: root.after(0, on_search_done, dados)),
        daemon=True
    )
    thread.start()

# --- INTERFACE GRÁFICA ---
root = tk.Tk()
root.title("Busca de Condomínios 🏙️")
root.geometry("480x330")
root.resizable(False, False)

style = ttk.Style()
style.configure("TLabel", font=("Segoe UI", 10))
style.configure("TButton", font=("Segoe UI", 10, "bold"))
style.configure("TCombobox", font=("Segoe UI", 10))

ttk.Label(root, text="Selecione a Cidade:").pack(pady=(16, 6))
combo_cidade = ttk.Combobox(root, values=list(locais.keys()), state="readonly", width=30)
combo_cidade.pack()

ttk.Label(root, text="Selecione o Bairro:").pack(pady=(12, 6))
combo_bairro = ttk.Combobox(root, state="readonly", width=30)
combo_bairro.pack()

def atualizar_bairros(event):
    cidade_selecionada = combo_cidade.get()
    bairros = locais.get(cidade_selecionada, [])
    combo_bairro["values"] = bairros
    if bairros:
        combo_bairro.current(0)

combo_cidade.bind("<<ComboboxSelected>>", atualizar_bairros)

progress = ttk.Progressbar(root, mode='indeterminate', length=360)
progress.pack(pady=(18, 6))

btn_buscar = ttk.Button(root, text="🔍 Buscar Condomínios", command=buscar_condominios)
btn_buscar.pack(pady=12)

ttk.Label(root, text="© BotNerd - Automatik PRO", font=("Segoe UI", 8, "italic")).pack(side="bottom", pady=8)

root.mainloop()
