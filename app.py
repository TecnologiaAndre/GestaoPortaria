import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.express as px  # Para o Gráfico de Ocupação

# 1. Configuração da Página
st.set_page_config(page_title="Controle de Portaria", page_icon="🛃", layout="wide")

# 2. Conexão Secura com o Supabase (Estilo Nuvem)
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

# 4. Função para Validar o Login usando Nome e a coluna Senha (Versão Blindada)
def realizar_login(usuario, senha):
    try:
        usuario_limpo = usuario.strip()
        senha_limpa = senha.strip()
        
        resposta = supabase.table("cadastro_porteiros")\
            .select("nome_porteiro")\
            .eq("nome_porteiro", usuario_limpo)\
            .eq("senha", senha_limpa)\
            .execute()
        
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
                    
    st.stop()

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
            destino_sel = st.selectbox("🏢 Local", options=locais)
            situacao_sel = st.selectbox("🔄 Situação", options=["Saindo da Garagem", "Retornando à Garagem"])
            
            fuso_brasilia = ZoneInfo("America/Sao_Paulo")
            agora_brasilia = datetime.now(fuso_brasilia)
            
            data_atual = agora_brasilia.date()
            hora_atual = agora_brasilia.time().strftime("%H:%M:%S")
            st.info(f"📅 **Data:** {data_atual.strftime('%d/%m/%Y')} | ⏰ **Hora:** {hora_atual}")

        botao_salvar = st.form_submit_button(label="💾 Gravar no Controle de Portaria")

    if botao_salvar:
        registro_movimentacao = {
            "data": str(data_atual),
            "hora": hora_atual,
            "veiculo": veiculo_sel,
            "motorista": motorista_sel,
            "destino": destino_sel,
            "situacao": situacao_sel,
            "porteiro": st.session_state.usuario_logado
        }
        
        try:
            supabase.table("controle_de_portaria").insert(registro_movimentacao).execute()
            st.success(f"✅ Registrado com sucesso para {veiculo_sel}!")
        except Exception as e:
            st.error(f"❌ Erro ao salvar movimentação: {e}")

with aba_historico:
    st.subheader("Laboratório de Testes Visuais")
    
    col_refresh, col_selector = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Atualizar Dados"):
            st.rerun()
            
    with col_selector:
        # Seletor dinâmico para você testar as 3 visões na hora
        visao_selecionada = st.radio(
            "Escolha o modelo de visualização para testar:",
            options=["1. Cartões de Status (Metrics)", "2. Linha do Tempo (Feed)", "3. Gráfico de Ocupação"],
            horizontal=True
        )
        
    st.write("---")
        
    try:
        resposta = supabase.table("controle_de_portaria").select("*").order("id", desc=True).limit(40).execute()
        
        if resposta.data:
            df = pd.DataFrame(resposta.data)
            df['datetime_completo'] = pd.to_datetime(df['data'] + ' ' + df['hora'])
            df = df.sort_values('datetime_completo', ascending=True)
            
            df['minutos_duracao'] = 0
            df['tempo_formatado'] = "-"
            
            # Cálculo de background das durações
            for i in range(len(df)):
                linha_atual = df.iloc[i]
                veiculo_atual = linha_atual['veiculo']
                time_atual = linha_atual['datetime_completo']
                
                df_anterior = df[(df['veiculo'] == veiculo_atual) & (df['datetime_completo'] < time_atual)]
                if not df_anterior.empty:
                    ultima_linha = df_anterior.iloc[-1]
                    diferenca = time_atual - ultima_linha['datetime_completo']
                    total_segundos = int(diferenca.total_seconds())
                    df.at[df.index[i], 'minutos_duracao'] = total_segundos // 60
                    
                    horas = total_segundos // 3600
                    minutos = (total_segundos % 3600) // 60
                    df.at[df.index[i], 'tempo_formatado'] = f"{horas}h {minutos}m" if horas > 0 else f"{minutos} min"

            df = df.sort_values('id', ascending=False)

            # ================= OPÇÃO 1: CARTÕES DE STATUS =================
            if visao_selecionada == "1. Cartões de Status (Metrics)":
                st.markdown("### 📋 Status Atual da Frota (Última Posição de Cada Veículo)")
                veiculos_unicos = df.drop_duplicates(subset=['veiculo'], keep='first')
                
                cols = st.columns(3)
                for idx, (_, car) in enumerate(veiculos_unicos.iterrows()):
                    col_atual = cols[idx % 3]
                    with col_atual:
                        if car['situacao'] == "Saindo da Garagem":
                            status_msg = "🟢 EM TRÂNSITO (RUA)"
                            sub_msg = f"Fora há: {car['tempo_formatado']}" if car['tempo_formatado'] != "-" else "Acabou de sair"
                        else:
                            status_msg = "🔵 NA GARAGEM (PÁTIO)"
                            sub_msg = f"Estacionado há: {car['tempo_formatado']}" if car['tempo_formatado'] != "-" else "Acabou de entrar"
                            
                        with st.container(border=True):
                            st.markdown(f"### {car['veiculo']}")
                            st.markdown(f"**Motorista:** {car['motorista']}")
                            st.markdown(f"**Último Local:** {car['destino']}")
                            st.metric(label=status_msg, value=sub_msg)

            # ================= OPÇÃO 2: LINHA DO TEMPO (FEED) =================
            elif visao_selecionada == "2. Linha do Tempo (Feed)":
                st.markdown("### 🕒 Feed de Movimentações Recentes (Estilo Linha do Tempo)")
                
                for _, linha in df.head(15).iterrows():
                    data_f = datetime.strptime(linha['data'], "%Y-%m-%d").strftime("%d/%m/%Y")
                    
                    if linha['situacao'] == "Saindo da Garagem":
                        icon, cor, acao = "🟢", "#d4edda", "SAÍDA REGISTRADA"
                        tempo_msg = f"⏱️ Fica no pátio antes de sair: **{linha['tempo_formatado']}**" if linha['tempo_formatado'] != "-" else ""
                    else:
                        icon, cor, acao = "🔵", "#cce5ff", "RETORNO À GARAGEM"
                        tempo_msg = f"⏱️ Tempo total da viagem na rua: **{linha['tempo_formatado']}**" if linha['tempo_formatado'] != "-" else ""
                        
                    st.markdown(
                        f"""
                        <div style="background-color: {cor}; padding: 15px; border-radius: 8px; margin-bottom: 12px; color: #155724 if icon=='🟢' else #004085;">
                            <h4 style="margin: 0;">{icon} {acao} — {data_f} às {linha['hora']}</h4>
                            <p style="margin: 5px 0 0 0;"><b>Veículo:</b> {linha['veiculo']} | <b>Motorista:</b> {linha['motorista']}</p>
                            <p style="margin: 2px 0 0 0;"><b>Local informado:</b> {linha['destino']} | <b>Porteiro:</b> {linha['porteiro']}</p>
                            <p style="margin: 5px 0 0 0; color: #555; font-style: italic;">{tempo_msg}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            # ================= OPÇÃO 3: GRÁFICO DE OCUPAÇÃO =================
            elif visao_selecionada == "3. Gráficos de Barra de Ocupação":
                st.markdown("### 📊 Análise de Tempo de Pátio vs. Tempo de Rua (Em minutos)")
                
                df_validos = df[df['minutos_duracao'] > 0]
                if not df_validos.empty:
                    fig = px.bar(
                        df_validos.head(20),
                        x="veiculo",
                        y="minutos_duracao",
                        color="situacao",
                        title="Duração das Últimas Movimentações por Veículo",
                        labels={"minutos_duracao": "Minutos Corridos", "veiculo": "Veículo", "situacao": "Evento"},
                        color_discrete_map={"Saindo da Garagem": "#2ecc71", "Retornando à Garagem": "#3498db"},
                        barmode="group"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Ainda não há dados acumulados suficientes para gerar o gráfico de tempo.")
                    
        else:
            st.info("Nenhum registro na tabela de controle ainda.")
    except Exception as e:
        st.error(f"Erro ao carregar laboratório de testes: {e}")