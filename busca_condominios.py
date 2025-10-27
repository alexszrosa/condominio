import tkinter as tk
from tkinter import ttk, messagebox
from serpapi import GoogleSearch
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import threading

# ---- CONFIG ----
API_KEY = # SUA_API_KEY_AQUI  # <--- coloque sua SerpApi key aqui

locais = {
    "São Paulo": ["Moema", "Pinheiros", "Tatuapé", "Santana", "Morumbi"],
    "Rio de Janeiro": ["Copacabana", "Barra da Tijuca", "Botafogo", "Tijuca", "Ipanema"],
    "Curitiba": ["Centro", "Água Verde", "Batel"],
    "Belo Horizonte": ["Savassi", "Funcionários", "Buritis"]
}
# ----------------

def worker_busca(cidade, bairro, on_done_callback):
    """Função que roda em thread separada — faz todo o trabalho de scraping."""
    dados = []
    try:
        query = f"lista de condomínios residenciais em {bairro}, {cidade}"
        params = {
            "engine": "google",
            "q": query,
            "google_domain": "google.com.br",
            "hl": "pt-BR",
            "num": "10",
            "api_key": API_KEY
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        links = [r["link"] for r in results.get("organic_results", []) if "link" in r]

        for link in links:
            try:
                resposta = requests.get(link, timeout=10)
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
                time.sleep(1.0)  # pausa curta para ser gentil com servidores
            except Exception as e:
                print(f"Erro ao acessar {link}: {e}")
    except Exception as e:
        print(f"Erro na busca SerpApi: {e}")

    # chama o callback na thread principal (GUI)
    on_done_callback(dados)

def on_search_done(dados):
    """Executado na thread principal quando worker terminar."""
    # para a barra de progresso e habilita botão
    progress.stop()
    btn_buscar.config(state="normal")

    if dados:
        nome_arquivo = f"condominios_{combo_cidade.get()}_{combo_bairro.get()}.xlsx".replace(" ", "_")
        df = pd.DataFrame(dados)
        df.to_excel(nome_arquivo, index=False)
        messagebox.showinfo("Concluído", f"✅ Planilha criada: {nome_arquivo}")
        pd.read_excel(nome_arquivo)
    else:
        messagebox.showinfo("Resultado", "⚠️ Nenhum dado encontrado para essa busca.")

def buscar_condominios():
    cidade = combo_cidade.get()
    bairro = combo_bairro.get()
    if not cidade or not bairro:
        messagebox.showwarning("Aviso", "Selecione uma cidade e um bairro!")
        return

    # desabilita botão e inicia barra de progresso
    btn_buscar.config(state="disabled")
    progress.start(10)  # 10ms entre "frames" da animação

    # Inicia thread que fará o scraping e depois chamará on_search_done
    thread = threading.Thread(
        target=worker_busca,
        args=(cidade, bairro, lambda dados: root.after(0, on_search_done, dados)),
        daemon=True
    )
    thread.start()

# --- Cria a janela PRINCIPAL antes de criar qualquer widget ---
root = tk.Tk()
root.title("Busca de Condomínios 🏙️")
root.geometry("480x320")
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

# Barra de progresso (definida após root existir)
progress = ttk.Progressbar(root, mode='indeterminate', length=360)
progress.pack(pady=(18, 6))

btn_buscar = ttk.Button(root, text="🔍 Buscar Condomínios", command=buscar_condominios)
btn_buscar.pack(pady=12)

ttk.Label(root, text="© BotNerd - Automatik PRO", font=("Segoe UI", 8, "italic")).pack(side="bottom", pady=8)

root.mainloop()
