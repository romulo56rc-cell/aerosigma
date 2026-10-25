import math
import requests
import streamlit as st
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from streamlit_geolocation import streamlit_geolocation

# Configuração da Página Web
st.set_page_config(page_title="Aerosigma - Helipontos", page_icon="🚁", layout="centered")

st.title("🚁 AEROSIGMA Web")
st.subheader("Gerador Profissional de Heliponto (Posicionamento Final Exato)")
st.write("Planta técnica sincronizada com a biruta no canto inferior esquerdo e peso ajustado.")

class AerosigmaEngine:
    def __init__(self, lat, lon, alt_m, nome_projeto="Heliponto Aerosigma", peso_kg=5000):
        self.lat = lat
        self.lon = lon
        self.alt_m = alt_m
        self.nome_projeto = nome_projeto
        self.peso_kg = peso_kg
        self.R = 6378137.0

    def calcular_declinacao_magnetica(self):
        return -21.5  # Estimativa WMM Brasil

    def converter_rumo_verdadeiro_para_magnetico(self, rumo_verdadeiro):
        decl = self.calcular_declinacao_magnetica()
        rumo_mag = (rumo_verdadeiro - decl) % 360
        return round(rumo_mag, 1)

    def deslocar_ponto(self, lat, lon, distancia_m, azimute_deg):
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        azim_rad = math.radians(azimute_deg)
        d_r = distancia_m / self.R

        lat2_rad = math.asin(
            math.sin(lat_rad) * math.cos(d_r) +
            math.cos(lat_rad) * math.sin(d_r) * math.cos(azim_rad)
        )
        lon2_rad = lon_rad + math.atan2(
            math.sin(azim_rad) * math.sin(d_r) * math.cos(lat_rad),
            math.cos(d_r) - math.sin(lat_rad) * math.sin(lat2_rad)
        )
        return math.degrees(lat2_rad), math.degrees(lon2_rad)

    def gerar_fato_tlof_personalizada(self, tamanho_tlof_m):
        meio_fato = (tamanho_tlof_m * 1.25) / 2.0
        cantos_fato = [
            (-meio_fato, meio_fato),
            (meio_fato, meio_fato),
            (meio_fato, -meio_fato),
            (-meio_fato, -meio_fato)
        ]
        pontos_fato = []
        for dx, dy in cantos_fato:
            p_lat = self.lat + (dy / 111000.0)
            p_lon = self.lon + (dx / (111000.0 * math.cos(math.radians(self.lat))))
            pontos_fato.append((p_lat, p_lon, self.alt_m))
        pontos_fato.append(pontos_fato[0])
        return pontos_fato

    def gerar_geometria_tlof_e_marcas(self, tamanho_tlof_m, rumo_verdadeiro):
        meio_tlof = tamanho_tlof_m / 2.0
        cantos_tlof = [
            (-meio_tlof, meio_tlof),
            (meio_tlof, meio_tlof),
            (meio_tlof, -meio_tlof),
            (-meio_tlof, -meio_tlof)
        ]
        pontos_tlof = []
        for dx, dy in cantos_tlof:
            p_lat = self.lat + (dy / 111000.0)
            p_lon = self.lon + (dx / (111000.0 * math.cos(math.radians(self.lat))))
            pontos_tlof.append((p_lat, p_lon, self.alt_m + 0.1))
        pontos_tlof.append(pontos_tlof[0])

        h_largura = tamanho_tlof_m * 0.25
        h_altura = tamanho_tlof_m * 0.4
        h_espessura = tamanho_tlof_m * 0.05

        def coord_relativa(dx, dy):
            plat = self.lat + (dy / 111000.0)
            plon = self.lon + (dx / (111000.0 * math.cos(math.radians(self.lat))))
            return plat, plon, self.alt_m + 0.2

        h_esq = [
            coord_relativa(-h_largura/2, -h_altura/2),
            coord_relativa(-h_largura/2 + h_espessura, -h_altura/2),
            coord_relativa(-h_largura/2 + h_espessura, h_altura/2),
            coord_relativa(-h_largura/2, h_altura/2),
            coord_relativa(-h_largura/2, -h_altura/2)
        ]
        h_dir = [
            coord_relativa(h_largura/2 - h_espessura, -h_altura/2),
            coord_relativa(h_largura/2, -h_altura/2),
            coord_relativa(h_largura/2, h_altura/2),
            coord_relativa(h_largura/2 - h_espessura, h_altura/2),
            coord_relativa(h_largura/2 - h_espessura, -h_altura/2)
        ]
        h_meio = [
            coord_relativa(-h_largura/2, -h_espessura/2),
            coord_relativa(h_largura/2, -h_espessura/2),
            coord_relativa(h_largura/2, h_espessura/2),
            coord_relativa(-h_largura/2, h_espessura/2),
            coord_relativa(-h_largura/2, -h_espessura/2)
        ]

        tri_dist = meio_tlof * 0.75
        rad_rumo = math.radians(90 - rumo_verdadeiro)
        cx = tri_dist * math.cos(rad_rumo)
        cy = tri_dist * math.sin(rad_rumo)
        tam = tamanho_tlof_m * 0.08

        p1_x = cx + tam * math.cos(rad_rumo)
        p1_y = cy + tam * math.sin(rad_rumo)
        p2_x = cx + tam * math.cos(rad_rumo + math.radians(135))
        p2_y = cy + tam * math.sin(rad_rumo + math.radians(135))
        p3_x = cx + tam * math.cos(rad_rumo - math.radians(135))
        p3_y = cy + tam * math.sin(rad_rumo - math.radians(135))

        triangulo = [
            coord_relativa(p1_x, p1_y),
            coord_relativa(p2_x, p2_y),
            coord_relativa(p3_x, p3_y),
            coord_relativa(p1_x, p1_y)
        ]

        return pontos_tlof, [h_esq, h_dir, h_meio], triangulo

    def gerar_cone_aproximacao_3d(self, azimute_rampa_deg, comprimento_m=1200, inclinacao_rampa=8.0, abertura_deg=15):
        passos = 10
        delta_dist = comprimento_m / passos
        poligonos_cone = []

        for i in range(passos):
            d1 = i * delta_dist
            d2 = (i + 1) * delta_dist
            alt1 = self.alt_m + (d1 / inclinacao_rampa)
            alt2 = self.alt_m + (d2 / inclinacao_rampa)

            largura1 = 15.0 + (d1 * math.tan(math.radians(abertura_deg)))
            largura2 = 15.0 + (d2 * math.tan(math.radians(abertura_deg)))

            c1_lat, c1_lon = self.deslocar_ponto(self.lat, self.lon, d1, azimute_rampa_deg)
            c2_lat, c2_lon = self.deslocar_ponto(self.lat, self.lon, d2, azimute_rampa_deg)

            e1_lat, e1_lon = self.deslocar_ponto(c1_lat, c1_lon, largura1, azimute_rampa_deg - 90)
            d1_lat, d1_lon = self.deslocar_ponto(c1_lat, c1_lon, largura1, azimute_rampa_deg + 90)
            e2_lat, e2_lon = self.deslocar_ponto(c2_lat, c2_lon, largura2, azimute_rampa_deg - 90)
            d2_lat, d2_lon = self.deslocar_ponto(c2_lat, c2_lon, largura2, azimute_rampa_deg + 90)

            quad_3d = [
                (e1_lat, e1_lon, alt1),
                (d1_lat, d1_lon, alt1),
                (d2_lat, d2_lon, alt2),
                (e2_lat, e2_lon, alt2),
                (e1_lat, e1_lon, alt1)
            ]
            poligonos_cone.append(quad_3d)
        return poligonos_cone

    def exportar_kml(self, nome_ficheiro, pontos_fato, pontos_tlof, barras_h, triangulo, poligonos_cone, nome_proj):
        kml_header = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{nome_proj}</name>
    <Style id="estiloFato">
      <PolyStyle><color>40fc8181</color><fill>1</fill><outline>1</outline></PolyStyle>
      <LineStyle><color>ffe53e3e</color><width>3</width></LineStyle>
    </Style>
    <Style id="estiloTlof">
      <PolyStyle><color>f05d361a</color><fill>1</fill><outline>1</outline></PolyStyle>
      <LineStyle><color>ffffffff</color><width>2</width></LineStyle>
    </Style>
    <Style id="estiloMarcaBranca">
      <PolyStyle><color>ffffffff</color><fill>1</fill><outline>1</outline></PolyStyle>
      <LineStyle><color>ffffffff</color><width>1</width></LineStyle>
    </Style>
    <Style id="estiloTriangulo">
      <PolyStyle><color>ff4bc9ec</color><fill>1</fill><outline>1</outline></PolyStyle>
      <LineStyle><color>ff00ffff</color><width>2</width></LineStyle>
    </Style>
"""
        kml_body = """    <Placemark>
      <name>Área de Segurança FATO</name>
      <styleUrl>#estiloFato</styleUrl>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs><LinearRing><coordinates>\n"""
        for p in pontos_fato:
            kml_body += f"              {p[1]},{p[0]},{p[2]}\n"
        kml_body += """            </coordinates></LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>\n"""

        kml_body += """    <Placemark>
      <name>TLOF - Heliponto</name>
      <styleUrl>#estiloTlof</styleUrl>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs><LinearRing><coordinates>\n"""
        for p in pontos_tlof:
            kml_body += f"              {p[1]},{p[0]},{p[2]}\n"
        kml_body += """            </coordinates></LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>\n"""

        for idx, barra in enumerate(barras_h):
            kml_body += f"""    <Placemark>
      <name>Letra H - Parte {idx+1}</name>
      <styleUrl>#estiloMarcaBranca</styleUrl>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs><LinearRing><coordinates>\n"""
            for p in barra:
                kml_body += f"              {p[1]},{p[0]},{p[2]}\n"
            kml_body += """            </coordinates></LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>\n"""

        kml_body += """    <Placemark>
      <name>Triângulo Orientador</name>
      <styleUrl>#estiloTriangulo</styleUrl>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs><LinearRing><coordinates>\n"""
        for p in triangulo:
            kml_body += f"              {p[1]},{p[0]},{p[2]}\n"
        kml_body += """            </coordinates></LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>\n"""

        total_secoes = len(poligonos_cone)
        for idx, quad in enumerate(poligonos_cone):
            opacidade_hex = format(max(20, int(140 - (idx * (100 / total_secoes)))), '02x')
            estilo_id = f"estiloCone_{idx}"
            
            kml_header += f"""    <Style id="{estilo_id}">
      <PolyStyle><color>{opacidade_hex}00ffff</color><fill>1</fill><outline>1</outline></PolyStyle>
      <LineStyle><color>ffff00ff</color><width>1</width></LineStyle>
    </Style>\n"""

            kml_body += f"""    <Placemark>
      <name>Cone de Aproximação - Seção {idx+1}</name>
      <styleUrl>#{estilo_id}</styleUrl>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs><LinearRing><coordinates>\n"""
            for p in quad:
                kml_body += f"              {p[1]},{p[0]},{p[2]}\n"
            kml_body += """            </coordinates></LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>\n"""

        kml_footer = "  </Document>\n</kml>"
        with open(nome_ficheiro, "w", encoding="utf-8", errors="ignore") as f:
            f.write(kml_header + kml_body + kml_footer)

    def gerar_planta_pdf(self, nome_arquivo_pdf, tamanho_tlof_m, rumo_verdadeiro):
        decl = self.calcular_declinacao_magnetica()
        rumo_mag = self.converter_rumo_verdadeiro_para_magnetico(rumo_verdadeiro)

        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.set_aspect('equal')
        ax.set_xlim(-65, 65)
        ax.set_ylim(-65, 65)

        raios_gradiente = np.linspace(60, 15, 10)
        for idx, r in enumerate(raios_gradiente):
            alpha_val = 0.08 + (len(raios_gradiente) - idx) * 0.025
            circ_grad = patches.Circle((0, 0), r, color='#2B6CB0', alpha=alpha_val, linewidth=0)
            ax.add_patch(circ_grad)

        rad_rumo = math.radians(90 - rumo_verdadeiro)
        for i in range(6, 0, -1):
            dist_faixa = i * 9.0
            alfa_faixa = 0.06 + (i * 0.03)
            wedge = patches.Wedge((0, 0), dist_faixa, rumo_verdadeiro - 90 - 12, rumo_verdadeiro - 90 + 12, 
                                  facecolor='#3182CE', alpha=alfa_faixa, edgecolor=None)
            ax.add_patch(wedge)

        lado_fato = tamanho_tlof_m * 1.25
        fato = patches.Rectangle((-lado_fato/2, -lado_fato/2), lado_fato, lado_fato, 
                                 linewidth=2, edgecolor='#E53E3E', facecolor='#FED7D7', alpha=0.6, 
                                 linestyle='--', label=f'FATO de Segurança')
        ax.add_patch(fato)

        tlof = patches.Rectangle((-tamanho_tlof_m/2, -tamanho_tlof_m/2), tamanho_tlof_m, tamanho_tlof_m, 
                                 linewidth=2.5, edgecolor='white', facecolor='#1A365D', alpha=0.98, 
                                 label=f'TLOF Principal ({tamanho_tlof_m}m)')
        ax.add_patch(tlof)

        # Letra H central perfeitamente limpa e visível
        ax.text(0, 0, 'H', color='white', fontsize=32, fontweight='bold', ha='center', va='center')

        # Indicação de Peso Máximo (5.0t) com fonte menor e posicionada na diagonal inferior esquerda
        ax.text(-5.0, -3.5, f"{self.peso_kg/1000:.1f}t", color='white', fontsize=6.0, fontweight='bold', ha='center', va='center', bbox=dict(boxstyle="square,pad=0.15", facecolor="#2B6CB0", edgecolor="white"))

        # Cota de tamanho "20 m" na borda superior direita
        ax.text(tamanho_tlof_m/2 - 4.5, tamanho_tlof_m/2 - 2.0, f"{int(tamanho_tlof_m)} m", color='white', fontsize=9, fontweight='bold', ha='center', va='center', bbox=dict(boxstyle="square,pad=0.2", facecolor="#1A365D", edgecolor="white"))

        # Duas setas no canto superior esquerdo
        ax.annotate('', xy=(-3.0, 5.0), xytext=(-3.0, 8.0), arrowprops=dict(arrowstyle="->", color="white", lw=2.5))
        ax.annotate('', xy=(-6.5, 5.0), xytext=(-6.5, 2.0), arrowprops=dict(arrowstyle="->", color="white", lw=2.5))

        # Biruta posicionada exatamente no CANTO INFERIOR ESQUERDO (no local do ponto branco)
        biruta_x, biruta_y = -tamanho_tlof_m/2 + 2.5, -tamanho_tlof_m/2 + 2.5
        ax.plot([biruta_x, biruta_x], [biruta_y, biruta_y + 3.0], color='black', linewidth=1.5)
        biruta_cone = patches.Polygon([[biruta_x, biruta_y + 3.0], [biruta_x + 3.0, biruta_y + 2.2], [biruta_x + 3.0, biruta_y + 0.8]], color='#DD6B20')
        ax.add_patch(biruta_cone)
        ax.text(biruta_x + 1.5, biruta_y + 4.0, 'BIRUTA', fontsize=5, fontweight='bold', color='white', ha='center')

        tri_dist = tamanho_tlof_m / 2.0 * 0.75
        tri_x = tri_dist * math.cos(rad_rumo)
        tri_y = tri_dist * math.sin(rad_rumo)
        triangle = patches.RegularPolygon((tri_x, tri_y), numVertices=3, radius=3.0, 
                                          orientation=rad_rumo - math.pi/2, color='#ECC94B')
        ax.add_patch(triangle)

        rx = 52 * math.cos(rad_rumo)
        ry = 52 * math.sin(rad_rumo)
        ax.plot([0, rx], [0, ry], color='#2B6CB0', linestyle='-', linewidth=3, label=f'Eixo Aprox: {rumo_verdadeiro}°V / {rumo_mag}°M')

        plt.title(f"AEROSIGMA - PLANTA TÉCNICA DE HELIPONTO\nProjeto: {self.nome_projeto}", fontsize=12, fontweight='bold', pad=20)
        ax.legend(loc='lower left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.6)

        info_text = (
            f" ESPECIFICAÇÕES TÉCNICAS DA INFRAESTRUTURA:\n"
            f" -------------------------------------------------------------------\n"
            f" Coordenadas do Centro : Lat {self.lat:.6f}° | Lon {self.lon:.6f}°\n"
            f" Altitude de Referência  : {self.alt_m} m (MSL)\n"
            f" Peso Máx. da Aeronave (MTOW): {self.peso_kg:,.1f} kg\n"
            f" Dimensão do Heliponto (TLOF): {tamanho_tlof_m} metros\n"
            f" Declinação Magnética  : {decl}° W\n"
            f" Orientação Rumo       : {rumo_verdadeiro}° (Verdadeiro) -> {rumo_mag}° (Magnético)\n"
            f" Norma Reguladora      : RBAC 154 / ICA 63-19\n"
        )
        fig.text(0.12, 0.08, info_text, fontsize=9, bbox=dict(boxstyle="round,pad=0.5", facecolor="#EDF2F7", edgecolor="#CBD5E0"))

        plt.tight_layout()
        plt.subplots_adjust(bottom=0.31)

        with PdfPages(nome_arquivo_pdf) as pdf:
            pdf.savefig(fig)
        plt.close()

# Interface Web com Streamlit
st.sidebar.header("⚙️ Parâmetros do Heliponto")

st.sidebar.markdown("### 📍 Obter Posição GPS")
loc = streamlit_geolocation()

if 'lat_input' not in st.session_state:
    st.session_state.lat_input = -23.550520
if 'lon_input' not in st.session_state:
    st.session_state.lon_input = -46.633308
if 'alt_input' not in st.session_state:
    st.session_state.alt_input = 760.0

if loc and loc.get('latitude') and loc.get('longitude'):
    st.session_state.lat_input = float(loc['latitude'])
    st.session_state.lon_input = float(loc['longitude'])
    
    try:
        url_elev = f"https://api.open-elevation.com/api/v1/lookup?locations={loc['latitude']},{loc['longitude']}"
        res = requests.get(url_elev, timeout=3).json()
        if 'results' in res and len(res['results']) > 0:
            st.session_state.alt_input = float(res['results'][0]['elevation'])
    except:
        pass

    st.sidebar.success("GPS OK! Coordenadas e Altitude atualizadas.")

nome_proj = st.sidebar.text_input("Nome do Projeto", "Heliponto 20m - 5t", key="nome_projeto")

lat = st.sidebar.number_input("Latitude", format="%.6f", key="lat_input")
lon = st.sidebar.number_input("Longitude", format="%.6f", key="lon_input")
alt = st.sidebar.number_input("Altitude (metros MSL)", format="%.1f", key="alt_input")

opcoes_peso = {
    "3 Toneladas (3.000 kg)": 3000.0,
    "5 Toneladas (5.000 kg)": 5000.0,
    "8 Toneladas (8.000 kg)": 8000.0,
    "12 Toneladas (12.000 kg)": 12000.0
}
escolha_peso_txt = st.sidebar.selectbox("Peso Máximo da Aeronave (MTOW)", list(opcoes_peso.keys()), index=1)
peso = opcoes_peso[escolha_peso_txt]

opcoes_tamanho = {
    "15 Metros (15m)": 15.0,
    "20 Metros (20m)": 20.0,
    "25 Metros (25m)": 25.0,
    "30 Metros (30m)": 30.0
}
escolha_tamanho_txt = st.sidebar.selectbox("Tamanho do Heliponto (TLOF)", list(opcoes_tamanho.keys()), index=1)
tamanho_tlof = opcoes_tamanho[escolha_tamanho_txt]

rumo = st.sidebar.slider("Rumo de Aproximação (°)", 0.0, 360.0, 140.0, key="rumo_aprox")

if st.button("🚀 Gerar Ficheiros do Heliponto", key="btn_gerar"):
    engine = AerosigmaEngine(lat, lon, alt, nome_projeto=nome_proj, peso_kg=peso)
    fato = engine.gerar_fato_tlof_personalizada(tamanho_tlof)
    tlof_pts, barras_h, triangulo = engine.gerar_geometria_tlof_e_marcas(tamanho_tlof, rumo)
    cone = engine.gerar_cone_aproximacao_3d(azimute_rampa_deg=rumo)
    
    nome_kml = f"{nome_proj.replace(' ', '_')}.kml"
    nome_pdf = f"Planta_Tecnica_{nome_proj.replace(' ', '_')}.pdf"

    engine.exportar_kml(nome_kml, fato, tlof_pts, barras_h, triangulo, cone, nome_proj)
    engine.gerar_planta_pdf(nome_pdf, tamanho_tlof, rumo)

    st.success("✅ Projeto gerado com sucesso!")

    with open(nome_pdf, "rb") as f:
        st.download_button("📄 Descarregar Planta em PDF", f, file_name=nome_pdf, mime="application/pdf", key="dl_pdf")

    with open(nome_kml, "rb") as f:
        st.download_button("🌍 Descarregar Ficheiro KML 3D", f, file_name=nome_kml, mime="application/vnd.google-earth.kml+xml", key="dl_kml")
