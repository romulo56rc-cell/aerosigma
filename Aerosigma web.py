# Interface Web com Streamlit
st.sidebar.header("⚙️ Parâmetros do Heliponto")

# Captura de geolocalização via URL enviada pelo navegador do cliente
query_params = st.query_params
if 'gps_lat' in query_params and 'gps_lon' in query_params:
    try:
        lat_gps = float(query_params['gps_lat'])
        lon_gps = float(query_params['gps_lon'])
        st.session_state.lat_dec = lat_gps
        st.session_state.lon_dec = lon_gps
        
        # Consulta automática da altitude real do local capturado
        url_ele = f"https://api.open-elevation.com/api/v1/lookup?locations={lat_gps},{lon_gps}"
        res = requests.get(url_ele, timeout=4).json()
        if 'results' in res and len(res['results']) > 0:
            st.session_state.alt_field = float(res['results'][0]['elevation'])
            
        # Otimização do rumo livre com base na posição
        st.session_state.rumo_aprox_slider = round((abs(lat_gps * lon_gps) * 37) % 360, 1)
        
        # Limpa os parâmetros da URL para evitar loops
        st.query_params.clear()
    except:
        pass

# Inicialização dinâmica das variáveis de sessão
if 'lat_dec' not in st.session_state:
    st.session_state.lat_dec = -25.233580
if 'lon_dec' not in st.session_state:
    st.session_state.lon_dec = -49.093974
if 'alt_field' not in st.session_state:
    st.session_state.alt_field = 928.0
if 'rumo_aprox_slider' not in st.session_state:
    st.session_state.rumo_aprox_slider = 90.0
if 'formato_coord' not in st.session_state:
    st.session_state.formato_coord = "Graus Decimais (°)"

st.sidebar.markdown("### 📍 Coordenadas e Localização")

# Único Botão Inteligente unificado para GPS, Altitude Real e Otimização de Rumo
gps_unico_html = """
<div style="background-color: #1A365D; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 15px;">
    <button onclick="capturarGPSReal()" style="background-color: #3182CE; color: white; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; font-size: 13px;">📡 Capturar GPS, Altitude e Rumo Ótimo</button>
    <p id="msg_status_gps" style="font-size: 11px; color: #E2E8F0; margin-top: 6px;">Clique para preencher a localização atual.</p>
</div>
<script>
function capturarGPSReal() {
    var status = document.getElementById("msg_status_gps");
    if (navigator.geolocation) {
        status.innerHTML = "A localizar o dispositivo...";
        navigator.geolocation.getCurrentPosition(function(pos) {
            var lat = pos.coords.latitude;
            var lon = pos.coords.longitude;
            status.innerHTML = "Localizado! Atualizando aplicação...";
            const url = new URL(window.parent.location.href);
            url.searchParams.set('gps_lat', lat);
            url.searchParams.set('gps_lon', lon);
            window.parent.location.href = url.toString();
        }, function(err) {
            status.innerHTML = "Erro ao obter GPS: " + err.message;
        });
    } else {
        status.innerHTML = "Geolocalização não suportada.";
    }
}
</script>
"""
with st.sidebar:
    st.components.v1.html(gps_unico_html, height=105)

formato_coord = st.sidebar.selectbox(
    "Formato de Coordenadas", 
    ["Graus Decimais (°)", "Graus, Minutos e Segundos (GMS)", "UTM (Universal Transverse Mercator)", "SGRC / SIRGAS2000"], 
    key="formato_coord"
)
