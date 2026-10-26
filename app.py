import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONSTANTES DE DESIGN (PADRÃO SÊNIOR) ---
FONT_FAMILY = "Arial"
COLOR_BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0, "alpha": 1.0}
COLOR_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0, "alpha": 1.0}

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="Atualizador de Listas - Drive", page_icon="⚡", layout="centered")
st.title("⚡ Gerenciador de Listas Contínuas")
st.markdown("### Insere blocos de dados com cabeçalhos repetidos e design automático")

# --- FORMULÁRIO DE ENTRADA ---
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        nome_planilha_drive = st.text_input("Nome EXATO da Planilha no Drive:", value="Sua Planilha Existente")
    with col2:
        nome_aba_drive = st.text_input("Nome da Aba (ex: BANKER BAIA 03):", value="BANKER BAIA 03")

with st.container():
    status_selecionado = st.selectbox(
        "Status de Apoio para esta Lista:",
        ["PENDENTE", "APOIANDO", "NÃO APOIANDO", "URNA SIM", "URNA NÃO"]
    )

st.markdown("---")
arquivo_carregado = st.file_uploader("Arraste o arquivo .csv da nova lista aqui", type=["csv"])


# --- CAMADA DE SERVIÇOS E PROCESSAMENTO DE DADOS ---
def tratar_dados_csv(upload_file, status_apoio) -> list:
    """Lê o arquivo CSV, padroniza as colunas e higieniza os dados."""
    df = pd.read_csv(upload_file, sep=";")
    df.columns = [str(col).strip().upper() for col in df.columns]
    
    dados_limpos = []
    for _, row in df.iterrows():
        nome = str(row.get("APOIADOR", "")).strip().upper()
        telefone = str(row.get("CONTATO", "")).strip()
        
        # Validação de regras de negócio
        whatsapp = "INVÁLIDO" if pd.isna(row.get("CONTATO")) or telefone == "" else "VÁLIDO"
        
        sit_eleitoral = str(row.get("SITUAÇÃO ELEITORAL", "")).upper()
        situacao = "VÁLIDO" if "REGULAR" in sit_eleitoral else "A VERIFICAR"
        
        cpf_val = row.get("CPF", "")
        cpf_status = "INVÁLIDO" if pd.isna(cpf_val) or str(cpf_val).strip() == "" else "VÁLIDO"
        
        dados_limpos.append([nome, telefone, whatsapp, situacao, cpf_status, status_apoio])
        
    return dados_limpos


def obter_cliente_google() -> gspread.Client:
    """Instancia o cliente gspread isolando o escopo de autenticação local."""
    escopos = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credenciais = ServiceAccountCredentials.from_json_keyfile_name("chaves.json", escopos)
    return gspread.authorize(credenciais)


# --- FLUXO DE EXECUÇÃO PRINCIPAL ---
if arquivo_carregado is not None:
    if st.button("🚀 Injetar Nova Lista com Cabeçalho", use_container_width=True):
        try:
            with st.spinner("Processando lote e injetando dados na planilha..."):
                
                # 1. Extração e Transformação
                novos_dados = tratar_dados_csv(arquivo_carregado, status_selecionado)
                
                # 2. Conectividade Google Sheets
                cliente_google = obter_cliente_google()
                planilha = cliente_google.open(nome_planilha_drive)
                aba = planilha.worksheet(nome_aba_drive)

                # 3. Mapeamento de Índices e Coordenadas da Planilha
                valores_existentes = aba.get_all_values()
                linha_atual = len(valores_existentes)

                # Calcula início respeitando respiro visual
                linha_inicio_bloco = (linha_atual + 2) if linha_atual > 0 else 1
                
                linha_banner_preto = linha_inicio_bloco
                linha_titulos_colunas = linha_inicio_bloco + 1
                linha_inicio_dados = linha_inicio_bloco + 2
                linha_fim_dados = linha_inicio_dados + len(novos_dados) - 1

                # Conversão para Índice Base Zero (exigido pela API em Batch Updates)
                idx_banner_zero = linha_banner_preto - 1
                idx_titulos_zero = linha_titulos_colunas - 1
                idx_dados_zero = linha_inicio_dados - 1

                # 4. Estruturação do Payload de Conteúdo (Texto Fixo Automático)
                payload_conteudo = [
                    [" - LÍDER DE REDE", "", "", "", "", ""],
                    ["NOME", "TELEFONE", "WHATSAPP", "SITUAÇÃO ELEITORAL", "CPF / DN", "APOIO"]
                ]
                payload_conteudo.extend(novos_dados)

                # 5. Construção da Fila de Formatação (Batch Requests)
                aba_id = aba.id
                fila_requisicoes = []

                # Operação 1: Reset de validações de dados nas linhas de cabeçalho
                fila_requisicoes.append({
                    "setDataValidation": {
                        "range": {
                            "sheetId": aba_id,
                            "startRowIndex": idx_banner_zero,
                            "endRowIndex": linha_titulos_colunas,
                            "startColumnIndex": 0,
                            "endColumnIndex": 6
                        }
                    }
                })

                # Operação 2: Fusão de células do Banner Principal (A:F)
                fila_requisicoes.append({
                    "mergeCells": {
                        "range": {
                            "sheetId": aba_id, 
                            "startRowIndex": idx_banner_zero, 
                            "endRowIndex": linha_banner_preto, 
                            "startColumnIndex": 0, 
                            "endColumnIndex": 6
                        },
                        "mergeType": "MERGE_ALL"
                    }
                })
                
                # Operação 3: Estilização do Banner Principal
                fila_requisicoes.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": aba_id, 
                            "startRowIndex": idx_banner_zero, 
                            "endRowIndex": linha_banner_preto, 
                            "startColumnIndex": 0, 
                            "endColumnIndex": 6
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": COLOR_BLACK,
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "textFormat": {
                                    "fontFamily": FONT_FAMILY, 
                                    "fontSize": 12, 
                                    "bold": True, 
                                    "italic": True, 
                                    "foregroundColor": COLOR_WHITE
                                }
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)"
                    }
                })
                
                # Operação 4: Estilização dos Títulos das Colunas
                fila_requisicoes.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": aba_id, 
                            "startRowIndex": idx_titulos_zero, 
                            "endRowIndex": linha_titulos_colunas, 
                            "startColumnIndex": 0, 
                            "endColumnIndex": 6
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": COLOR_BLACK,
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "textFormat": {
                                    "fontFamily": FONT_FAMILY, 
                                    "fontSize": 10, 
                                    "bold": True, 
                                    "foregroundColor": COLOR_WHITE
                                }
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)"
                    }
                })

                # Operação 5: Alinhamento da Coluna de Nomes (Esquerda)
                fila_requisicoes.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": aba_id, 
                            "startRowIndex": idx_dados_zero, 
                            "endRowIndex": linha_fim_dados, 
                            "startColumnIndex": 0, 
                            "endColumnIndex": 1
                        },
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE"}},
                        "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                    }
                })

                # Operação 6: Alinhamento das Colunas de Metadados (Centro)
                fila_requisicoes.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": aba_id, 
                            "startRowIndex": idx_dados_zero, 
                            "endRowIndex": linha_fim_dados, 
                            "startColumnIndex": 1, 
                            "endColumnIndex": 6
                        },
                        "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE"}},
                        "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                    }
                })

                # 6. Despacho das Requisições visuais em Lote (Batch Update)
                planilha.batch_update({"requests": fila_requisicoes})

                # 7. Escrita de Dados Final via Range Único (Otimização de I/O)
                intervalo_destino = f"A{linha_inicio_bloco}:F{linha_fim_dados}"
                aba.update(range_name=intervalo_destino, values=payload_conteudo, value_input_option="USER_ENTERED")

            st.success(f"🎉 Bloco de dados alocado com sucesso a partir da linha {linha_inicio_bloco}!")
            st.caption("O cabeçalho foi estruturado e o marcador '- LÍDER DE REDE' foi fixado automaticamente.")
            st.balloons()

        except Exception as e:
            st.error(f"Falha na execução do pipeline: {e}")