import streamlit as st
from supabase import create_client, Client
from datetime import datetime

# 1. Configuração da Página
st.set_page_config(page_title="Controle de Portaria", page_icon="🛃", layout="wide")

# 2. Conexão Segura com o Supabase (Estilo Nuvem)
# O Streamlit Cloud lerá automaticamente essas variáveis da área de 'Secrets'
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# 3. Inicialização do Estado da Sessão (Controle de Login)
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None

# 4. Função para Validar o Login usando Nome e a coluna Senha
def realizar_login(usuario, senha):
    try:
        # Busca no banco filtrando por nome E por senha idêntica
        resposta = supabase.table("cadastro_porteiros")\
            .select("nome_porteiro")\
            .eq("nome_porteiro", usuario)\
            .eq("senha", senha)\
            .execute()
        
        # Se retornar dados, significa que a combinação usuário + senha está correta
        if resposta.data:
            st.session_state.autenticado = True
            st.session_state.usuario_logado = resposta.data[0]["nome_porteiro"]
            st.success(f"🔓 Bem-vindo, {st.session_state.usuario_logado}!")
            st.rerun()
        else:
            st.error("❌ Usuário ou senha incorretos. Verifique os dados informados.")
    except Exception as e:
        st.error(f"Erro ao conectar com a tabela de autenticação: {e}")

# 5. TELA DE LOGIN OBRIGATÓRIA
if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center;'>🛃 Acesso Restrito - Portaria</h2>", unsafe_allow_html=True)
    
    # Centraliza o formulário na tela para ficar visualmente limpo
    _, col_central, _ = st.columns([1, 2, 1])
    
    with col_central:
        with st.form(key="form_login", clear_on_submit=False):
            usuario_input = st.text_input("👤 Nome do Porteiro (Usuário)")
            senha_input = st.text_input("🔑 Senha", type="password")
            botao_login = st.form_submit_button("Efetuar Login")
            
            if botao_login:
                if usuario_input and senha_input:
                    realizar_login(usuario_input, senha_input)
                else:
                    st.warning("Por favor, preencha os campos de Usuário e Senha.")
                    
    st.stop() # Bloqueia absolutamente tudo abaixo caso o porteiro não esteja logado

# --- 🔓 ÁREA SEGURA (SÓ ACESSÍVEL SE ESTIVER AUTENTICADO) ---

# 6. Busca de Dados das Tabelas de Cadastro
@st.cache_data(ttl=60)
def carregar_dados_cadastro():
    try:
        motoristas_data = supabase.table("cadastro_motoristas").select("nome_motorista, matricula").order("nome_motorista").execute().data
        veiculos_data = supabase.table("cadastro_veiculos").select("veiculo, placa").order("veiculo").execute().data
        locais_data = supabase.table("cadastro_locais").select("nome_local").order("nome_local").execute().data
        
        lista_motoristas = [f"{m['nome_motorista']} ({m['matricula']})" for m in motoristas_data if m.get("nome_motorista")]
        lista_veiculos = [f"{v['veiculo']} - {v['placa']}".upper() for v in veiculos_data if v.get("veiculo")]
        lista_locais = [l["nome_local"] for l in locais_data if l.get("nome_local")]
        
        return lista_motoristas, lista_veiculos, lista_locais
    except Exception as e:
        st.error(f"Erro ao conectar com o banco: {e}")
        return [], [], []

motoristas, veiculos, locais = carregar_dados_cadastro()

if not motoristas: motoristas = ["Nenhum motorista encontrado"]
if not veiculos: veiculos = ["Nenhum veículo encontrado"]
if not locais: locais = ["Nenhum local encontrado"]

# --- INTERFACE PRINCIPAL ---
col_titulo, col_user = st.columns([4, 1.2])
with col_titulo:
    st.title("🛃 Sistema Integrado de Portaria")
with col_user:
    st.markdown(f"**Operador atual:**\n`{st.session_state.usuario_logado}`")
    if st.button("🚪 Encerrar Turno (Sair)"):
        st.session_state.autenticado = False
        st.session_state.usuario_logado = None
        st.rerun()

st.write("---")

aba_registro, aba_historico = st.tabs(["📝 Registrar Movimentação", "📊 Histórico de Registros"])

with aba_registro:
    if st.button("🔄 Atualizar Listas"):
        st.cache_data.clear()
        st.rerun()

    with st.form(key="form_portaria", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            motorista_sel = st.selectbox("👤 Motorista", options=motoristas)
            veiculo_sel = st.selectbox("🚗 Veículo / Placa", options=veiculos)
            
        with col2:
            destino_sel = st.selectbox("🏢 Local de Destino", options=locais)
            retorno_sel = st.selectbox("🔄 Local de Retorno / Situação", options=["Retorno à Garagem", "Saída Definitiva"] + locais)
            
            data_atual = datetime.now().date()
            hora_atual = datetime.now().time().strftime("%H:%M:%S")
            st.info(f"📅 **Data:** {data_atual.strftime('%d/%m/%Y')} | ⏰ **Hora:** {hora_atual}")

        botao_salvar = st.form_submit_button(label="💾 Gravar no Controle de Portaria")

    if botao_salvar:
        registro_movimentacao = {
            "data": str(data_atual),
            "hora": hora_atual,
            "veiculo": veiculo_sel,
            "motorista": motorista_sel,
            "destino": destino_sel,
            "retorno": retorno_sel,
            "porteiro": st.session_state.usuario_logado
        }
        
        try:
            supabase.table("controle_de_portaria").insert(registro_movimentacao).execute()
            st.success(f"✅ Registrado com sucesso para {veiculo_sel}!")
        except Exception as e:
            st.error(f"❌ Erro ao salvar movimentação: {e}")

with aba_historico:
    st.subheader("Últimos Registros")
    if st.button("🔄 Atualizar Tabela"):
        st.rerun()
        
    try:
        resposta = supabase.table("controle_de_portaria").select("*").order("id", desc=True).limit(20).execute()
        if resposta.data:
            st.dataframe(resposta.data, use_container_width=True)
        else:
            st.info("Nenhum registro na tabela de controle ainda.")
    except Exception as e:
        st.error(f"Erro ao buscar histórico: {e}")