import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import io
import hashlib

# ==============================================================================
# 1. CONFIGURAÇÃO E INFRAESTRUTURA
# ==============================================================================

st.set_page_config(page_title="Controle de Portaria", page_icon="🛃", layout="wide")

# Inicialização segura do Supabase usando Secrets do Streamlit para evitar hardcoding.
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_supabase() -> Client:
    """Garante uma única instância de conexão com o banco (Singleton/Resource)."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()


# ==============================================================================
# 2. SEGURANÇA, SESSÃO E AUTENTICAÇÃO
# ==============================================================================

def gerar_hash_senha(senha: str) -> str:
    """Criptografia padrão para senhas definitivas (atendimento à LGPD)."""
    return hashlib.sha256(senha.strip().encode('utf-8')).hexdigest()

# Inicialização do Session State para persistência de estado entre interações do Streamlit.
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "fase_troca_senha" not in st.session_state:
    st.session_state.fase_troca_senha = False
if "usuario_pendente_senha" not in st.session_state:
    st.session_state.usuario_pendente_senha = None


def realizar_login(usuario, senha):
    """
    Fluxo de Autenticação Híbrido:
    - Se for o primeiro acesso, valida o texto limpo gerado pelo painel admin.
    - Se for acesso recorrente, criptografa a entrada e compara com o Hash SHA-256 do banco.
    """
    try:
        usuario_limpo = usuario.strip()
        senha_limpa = senha.strip()
        
        resposta = supabase.table("cadastro_porteiros")\
            .select("nome_porteiro, senha, primeiro_acesso")\
            .eq("nome_porteiro", usuario_limpo)\
            .execute()
        
        if resposta.data:
            registro = resposta.data[0]
            senha_banco = registro.get("senha")
            eh_primeiro_acesso = registro.get("primeiro_acesso")
            
            if eh_primeiro_acesso is True:
                # Regra de Negócio: Senhas provisórias de novos porteiros ficam em texto limpo criadas via Admin
                if senha_limpa == senha_banco:
                    st.session_state.fase_troca_senha = True
                    st.session_state.usuario_pendente_senha = registro["nome_porteiro"]
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta para o primeiro acesso.")
            
            else:
                # Senhas normais já passaram pelo fluxo de transição e estão em Hash
                senha_digitada_hash = gerar_hash_senha(senha_limpa)
                if senha_digitada_hash == senha_banco:
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = registro["nome_porteiro"]
                    st.success(f"🔓 Bem-vindo, {st.session_state.usuario_logado}!")
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos.")
        else:
            st.error("❌ Usuário não cadastrado no sistema.")
            
    except Exception as e:
        st.error(f"Erro ao conectar com a tabela de autenticação: {e}")


# Guardrail de Fluxo: Impede a renderização do app caso o usuário não esteja logado
if not st.session_state.autenticado:
    
    # Sub-tela 1: Forçar Atualização de Credenciais no Primeiro Acesso
    if st.session_state.fase_troca_senha:
        st.markdown("<h2 style='text-align: center;'>🔒 Atualização de Segurança Obrigatória (LGPD)</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #555;'>Detectamos que este é o seu primeiro acesso. Por segurança, defina uma senha pessoal irreversível.</p>", unsafe_allow_html=True)
        
        _, col_central, _ = st.columns([1, 1.8, 1])
        with col_central:
            with st.form(key="form_troca_senha", clear_on_submit=True):
                st.info(f"Usuário: **{st.session_state.usuario_pendente_senha}**")
                nova_senha = st.text_input("Digite sua nova senha pessoal:", type="password")
                confirma_senha = st.text_input("Confirme a nova senha:", type="password")
                botao_mudar = st.form_submit_button("💾 Salvar Nova Senha em Hash e Entrar")
                
                if botao_mudar:
                    if not nova_senha or not confirma_senha:
                        st.warning("Por favor, preencha ambos os campos de senha.")
                    elif nova_senha != confirma_senha:
                        st.error("❌ As senhas digitadas não coincidem. Tente novamente.")
                    elif len(nova_senha) < 4:
                        st.warning("Por segurança, escolha uma senha com pelo menos 4 caracteres.")
                    else:
                        try:
                            # A senha trafega via SSL e é convertida localmente antes do INSERT no Supabase
                            nova_senha_hash = gerar_hash_senha(nova_senha)
                            
                            supabase.table("cadastro_porteiros")\
                                .update({"senha": nova_senha_hash, "primeiro_acesso": False})\
                                .eq("nome_porteiro", st.session_state.usuario_pendente_senha)\
                                .execute()
                            
                            st.session_state.autenticado = True
                            st.session_state.usuario_logado = st.session_state.usuario_pendente_senha
                            st.session_state.fase_troca_senha = False
                            st.session_state.usuario_pendente_senha = None
                            
                            st.success("🎉 Senha criptografada e salva com sucesso! Bem-vindo.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar nova senha no banco: {e}")
            
            if st.button("⬅️ Cancelar e Voltar"):
                st.session_state.fase_troca_senha = False
                st.session_state.usuario_pendente_senha = None
                st.rerun()
        st.stop()

    # Sub-tela 2: Interface de Autenticação Padrão
    else:
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


# ==============================================================================
# 3. ÁREA LOGADA / PROCESSAMENTO DE DADOS (DASHBOARD)
# ==============================================================================

fuso_brasilia = ZoneInfo("America/Sao_Paulo")
agora_brasilia = datetime.now(fuso_brasilia)
data_atual = agora_brasilia.date()
hora_atual = agora_brasilia.time().strftime("%H:%M:%S")


# Caching de tabelas auxiliares para otimizar custos e performance de requisições ao Supabase.
@st.cache_data(ttl=60)
def carregar_dados_cadastro():
    """Busca listas de apoio para alimentar os seletores da portaria. TTL de 60s."""
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

# Fallbacks defensivos para evitar que a UI quebre caso as tabelas estejam vazias.
if not motoristas: motoristas = ["Nenhum motorista encontrado"]
if not veiculos: veiculos = ["Nenhum veículo encontrado"]
if not locais: locais = ["Nenhum local encontrado"]


# --- COMPONENTE DE TOPO: IDENTIFICAÇÃO E LOGOUT ---
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

aba_registro, aba_historico, aba_plantao = st.tabs(["📝 Registrar Movimentação", "📊 Histórico de Registros", "🔄 Passagem de Plantão"])


# ================= ABA 1: REGISTRO DE MOVIMENTAÇÃO =================
with aba_registro:
    if st.button("🔄 Atualizar Listas"):
        st.cache_data.clear() # Limpa o cache para forçar nova requisição ao Supabase
        st.rerun()

    with st.form(key="form_portaria", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            motorista_sel = st.selectbox("👤 Motorista", options=motoristas)
            veiculo_sel = st.selectbox("🚗 Veículo / Placa", options=veiculos)
            
        with col2:
            destino_sel = st.selectbox("🏢 Local", options=locais)
            situacao_sel = st.selectbox("🔄 Situação", options=["Saindo da Garagem", "Retornando à Garagem"])
            
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


# ==============================================================================
# LOGICA CENTRAL: ENGENHARIA DE TEMPOS E ESTADOS DOS VEÍCULOS
# ==============================================================================
# Contexto Técnico: Como o banco salva eventos isolados (linhas de logs), nós reconstruímos a linha do tempo
# de forma programática. O algoritmo ordena os registros por tempo ascendente e varre comparando o estado atual 
# com o estado anterior daquele mesmo veículo para calcular o tempo decorrido na rua ou no pátio.

try:
    resposta = supabase.table("controle_de_portaria").select("*").order("id", desc=True).limit(60).execute()
    dados_carregados = resposta.data if resposta.data else []
except Exception as e:
    dados_carregados = []
    st.error(f"Erro ao conectar com o Supabase: {e}")

if dados_carregados:
    df_base = pd.DataFrame(dados_carregados)
    df_base['datetime_completo'] = pd.to_datetime(df_base['data'] + ' ' + df_base['hora'])
    df_base = df_base.sort_values('datetime_completo', ascending=True)
    
    # Inicialização das colunas de cálculo de métricas operacionais
    df_base['minutos_duracao'] = 0
    df_base['Tempo no Pátio'] = "-"
    df_base['Tempo em Trânsito'] = "-"
    
    # Algorítmo de reconstrução de estado e delta de tempo
    for i in range(len(df_base)):
        linha_atual = df_base.iloc[i]
        veiculo_atual = linha_atual['veiculo']
        sit_atual = linha_atual['situacao'] # Correção do bug 'presidential_sit' feita aqui
        time_atual = linha_atual['datetime_completo']
        
        # Localiza o histórico cronológico exclusivo deste veículo específico
        df_anterior = df_base[(df_base['veiculo'] == veiculo_atual) & (df_base['datetime_completo'] < time_atual)]
        if not df_anterior.empty:
            ultima_linha = df_anterior.iloc[-1]
            sit_anterior = ultima_linha['situacao']
            diferenca = time_atual - ultima_linha['datetime_completo']
            total_segundos = int(diferenca.total_seconds())
            
            df_base.at[df_base.index[i], 'minutos_duracao'] = total_segundos // 60
            horas = total_segundos // 3600
            minutos = (total_segundos % 3600) // 60
            tempo_formatado = f"{horas}h {minutos}m" if horas > 0 else f"{minutos} min"
            
            # Validação do par de eventos lógicos para atribuição correta das colunas
            if sit_atual == "Retornando à Garagem" and sit_anterior == "Saindo da Garagem":
                df_base.at[df_base.index[i], 'Tempo em Trânsito'] = tempo_formatado
            elif sit_atual == "Saindo da Garagem" and sit_anterior == "Retornando à Garagem":
                df_base.at[df_base.index[i], 'Tempo no Pátio'] = tempo_formatado

    # Organização de Visualização: Reverte para ordem descendente para exibição em tela de logs recentes
    df_base = df_base.sort_values('id', ascending=False)
    df_export = df_base.drop(columns=['datetime_completo', 'minutos_duracao'])
    colunas_ordenadas = ['id', 'data', 'hora', 'veiculo', 'motorista', 'destino', 'situacao', 'Tempo no Pátio', 'Tempo em Trânsito', 'porteiro']
    df_export = df_export.reindex(columns=colunas_ordenadas)
else:
    df_base = pd.DataFrame()
    df_export = pd.DataFrame()


# ================= ABA 2: HISTÓRICO PERSONALIZÁVEL =================
with aba_historico:
    if not df_export.empty:
        st.subheader("Painel de Monitoramento e Histórico")
        visao_definiva = st.radio(
            "Selecione o seu estilo preferido de exibição:",
            options=["📋 Tabela Clássica", "🗂️ Cartões de Status (Metrics)", "🕒 Linha do Tempo (Feed)", "📊 Gráfico de Ocupação"],
            horizontal=True,
            key="usuario_pref_vis"
        )
        st.write("---")
        
        if visao_definiva == "📋 Tabela Clássica":
            st.dataframe(df_export, use_container_width=True)
            
        elif visao_definiva == "🗂️ Cartões de Status (Metrics)":
            # Filtro para isolar apenas o último status conhecido de cada veículo (Visão de Pátio em Tempo Real)
            veiculos_unicos = df_base.drop_duplicates(subset=['veiculo'], keep='first')
            cols = st.columns(3)
            for idx, (_, car) in enumerate(veiculos_unicos.iterrows()):
                col_atual = cols[idx % 3]
                with col_atual:
                    if car['situacao'] == "Saindo da Garagem":
                        status_msg, sub_val = "🟢 EM TRÂNSITO (RUA)", car['Tempo em Trânsito'] if car['Tempo em Trânsito'] != "-" else "Em rota"
                    else:
                        status_msg, sub_val = "🔵 NA GARAGEM (PÁTIO)", car['Tempo no Pátio'] if car['Tempo no Pátio'] != "-" else "Estacionado"
                    with st.container(border=True):
                        st.markdown(f"### {car['veiculo']}")
                        st.markdown(f"👤 **Motorista:** {car['motorista']}  \n🏢 **Local:** {car['destino']}")
                        st.metric(label=status_msg, value=f"Duração: {sub_val}")
                        
        elif visao_definiva == "🕒 Linha do Tempo (Feed)":
            for _, linha in df_export.head(15).iterrows():
                data_f = datetime.strptime(linha['data'], "%Y-%m-%d").strftime("%d/%m/%Y")
                icon, cor = ("🟢", "#d4edda") if linha['situacao'] == "Saindo da Garagem" else ("🔵", "#cce5ff")
                st.markdown(f'<div style="background-color: {cor}; padding: 15px; border-radius: 8px; margin-bottom: 12px; color: #333;"><h4 style="margin:0;">{icon} {linha["situacao"].upper()} — {data_f} às {linha["hora"]}</h4><p style="margin:5px 0 0 0;"><b>Veículo:</b> {linha["veiculo"]} | <b>Motorista:</b> {linha["motorista"]} | <b>Local:</b> {linha["destino"]}</p><p style="margin:2px 0 0 0; font-size:13px; color:#555;">Operador: {linha["porteiro"]}</p></div>', unsafe_allow_html=True)
                
        elif visao_definiva == "📊 Gráfico de Ocupação":
            df_validos = df_base[df_base['minutos_duracao'] > 0].head(15)
            if not df_validos.empty:
                chart_data = df_validos.pivot_table(index='veiculo', columns='situacao', values='minutos_duracao', aggfunc='sum').fillna(0)
                st.bar_chart(chart_data)
        
        st.write("---")
        
        # Renderização do arquivo em memória para download via Streamlit sem salvar em disco local.
        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Controle Portaria')
        st.download_button(label="📥 Baixar Histórico Completo em Excel (.xlsx)", data=buffer_excel.getvalue(), file_name=f"relatorio_portaria_{agora_brasilia.strftime('%d_%m_%Y')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Nenhum registro para exibir.")


# ================= ABA 3: PASSAGEM DE PLANTÃO INTEGRADA =================
with aba_plantao:
    st.subheader("🔄 Fechamento e Passagem de Turno (Últimas 12 Horas)")
    st.write("Confira e audite as ocorrências do seu turno de 12 horas antes de salvar a passagem definitiva.")
    
    if not df_base.empty:
        # Filtro de auditoria retroativa com base no fuso-horário local configurado no topo.
        limite_12h = (agora_brasilia - timedelta(hours=12)).replace(tzinfo=None)
        df_12h = df_base[df_base['datetime_completo'] >= limite_12h]
        
        total_mov = len(df_12h)
        saidas_turno = len(df_12h[df_12h['situacao'] == "Saindo da Garagem"])
        retornos_turno = len(df_12h[df_12h['situacao'] == "Retornando à Garagem"])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("📊 Total de Movimentações (Últimas 12h)", total_mov)
        c2.metric("🟢 Saídas Registradas no Turno", saidas_turno)
        c3.metric("🔵 Retornos Registradas no Turno", retornos_turno)
        
        st.write("---")
        
        st.markdown("### 🚨 Veículos que se encontram na RUA atualmente:")
        # Identifica veículos órfãos de retorno para alertar o operador que está assumindo o turno.
        veiculos_ultimos = df_base.drop_duplicates(subset=['veiculo'], keep='first')
        carros_na_rua = veiculos_ultimos[veiculos_ultimos['situacao'] == "Saindo da Garagem"]
        
        if carros_na_rua.empty:
            st.success("✅ Tudo limpo! Nenhum veículo pendente na rua neste momento.")
        else:
            for _, pendencia in carros_na_rua.iterrows():
                st.warning(f"⚠️ **{pendencia['veiculo']}** — Com o motorista **{pendencia['motorista']}** (Destino: {pendencia['destino']} | Registro efetuado às {pendencia['hora']}).")
        
        st.write("---")
        
        st.markdown("### ✍️ Livro de Ocorrências e Assinatura Digital do Turno")
        with st.form(key="form_passagem_plantao"):
            obs_texto = st.text_area(
                "Insira avisos, problemas de infraestrutura ou recados para o próximo turno:", 
                placeholder="Ex: Deixei a chave do carro X no quadro B..."
            )
            botao_assinar = st.form_submit_button("🔒 Assinar e Gravar Fechamento de Plantão")
            
            if botao_assinar:
                if not carros_na_rua.empty:
                    lista_pendentes = ", ".join(carros_na_rua['veiculo'].tolist())
                else:
                    lista_pendentes = "Nenhum veículo pendente"

                dados_plantao = {
                    "data_fechamento": str(data_atual),
                    "hora_fechamento": hora_atual,
                    "porteiro_saindo": st.session_state.usuario_logado,
                    "total_movimentacoes": int(total_mov),
                    "veiculos_pendentes": lista_pendentes,
                    "observacoes": obs_texto
                }
                
                try:
                    supabase.table("passagem_plantao").insert(dados_plantao).execute()
                    st.success(f"🎉 Plantão de **{st.session_state.usuario_logado}** fechado e gravado com sucesso no Supabase!")
                    st.info("Deslogue do sistema clicando no botão '🚪 Encerrar Turno' lá em cima para dar lugar ao próximo operador.")
                except Exception as e:
                    st.error(f"❌ Erro crítico ao salvar o fechamento na tabela 'passagem_plantao': {e}")
    else:
        st.info("Ainda não existem dados no histórico para rodar o cálculo de auditoria de 12 horas.")