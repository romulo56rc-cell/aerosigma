import math
import streamlit as st
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from streamlit_geolocation import streamlit_geolocation

# Configuração da Página Web
st.set_page_config(page_title="Aerosigma - Helipontos", page_icon="🚁", layout="centered")

st.title("🚁 AEROSIGMA Web")
st.subheader("Gerador Profissional de Helipontos com GPS, KML & PDF")
st.write("Utilize a localização do telemóvel em campo ou insira os dados para gerar a infraestrutura regulada (RBAC 154 / ICA 63-19).")

class AerosigmaEngine:
    def __init__(self, lat, lon, alt_m, nome_projeto="Heliponto Aerosigma", peso_kg=3000):
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

    def gerar_fato_tlof_quadrada(self, d_rotor_m):
        meio_fato = (d_rotor_m * 1.5) / 2.0
        cantos_relativos = [
            (-meio_fato, meio_fato),
            (meio_fato, meio_fato),
            (meio_fato, -meio_fato),
            (-meio_fato, -meio_fato)
        ]
        pontos_fato = []
        for dx, dy in cantos_relativos:
            p_lat = self.lat + (dy / 111000.0)
            p_lon = self.lon + (dx / (111000.0 * math.cos(math.radians(self.lat))))
            pontos_fato.append((p_lat, p_lon, self.alt_m))
        pontos_fato.append(pontos_fato[0])
        return pontos_fato

    def gerar_cone_aproximacao_3d(self, azimute_rampa_deg, comprimento_m=1200, inclinacao_rampa=8.0, abertura_deg=15):
        passos = 10
        delta_dist = comprimento_m / passos
        poligonos_cone = []

        for i in range(passos):
            d1 = i * delta_dist
            d2 = (i + 1) * delta_dist
            alt1 = self.alt_m + (d1 / inclinacao_rampa)
            alt2 = self.alt_m + (d2 / inclinacao_rampa)

            largura1 = 10.0 + (d1 * math.tan(math.radians(abertura_deg)))
            largura2 = 10.0 + (d2 * math.tan(math.radians(abertura_deg)))

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

    def exportar_kml(self, nome_ficheiro, pontos_fato, poligonos_cone, nome_proj):
        kml_header = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{nome_proj}</name>
    <Style id="estiloFato">
      <PolyStyle><color>7dfc8181</color><fill>1</fill><outline>1</outline></PolyStyle>
      <LineStyle><color>ffe53e3e</color><width>3</width></LineStyle>
    </Style>
"""
        kml_body = """    <Placemark>
      <name>FATO Quadrada - Área de Segurança</name>
      <styleUrl>#estiloFato</styleUrl>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs><LinearRing><coordinates>\n"""
        for p in pontos_fato:
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

    def gerar_planta_pdf(self, nome_arquivo_pdf, d_rotor_m, rumo_verdadeiro):
        decl = self.calcular_declinacao_magnetica()
        rumo_mag = self.converter_rumo_verdadeiro_para_magnetico(rumo_verdadeiro)

        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.set_aspect('equal')
        ax.set_xlim(-60, 60)
        ax.set_ylim(-60, 60)

        raios_gradiente = np.linspace(55, 15, 10)
        for idx, r in enumerate(raios_gradiente):
            alpha_val = 0.08 + (len(raios_gradiente) - idx) * 0.025
            circ_grad = patches.Circle((0, 0), r, color='#2B6CB0', alpha=alpha_val, linewidth=0)
            ax.add_patch(circ_grad)

        rad_rumo = math.radians(90 - rumo_verdadeiro)
        for i in range(6, 0, -1):
            dist_faixa = i * 8.0
            alfa_faixa = 0.06 + (i * 0.03)
            wedge = patches.Wedge((0, 0), dist_faixa, rumo_verdadeiro - 90 - 12, rumo_verdadeiro - 90 + 12, 
                                  facecolor='#3182CE', alpha=alfa_faixa, edgecolor=None)
            ax.add_patch(wedge)

        lado_fato = d_rotor_m * 1.5
        fato = patches.Rectangle((-lado_fato/2, -lado_fato/2), lado_fato, lado_fato, 
                                 linewidth=2, edgecolor='#E53E3E', facecolor='#FED7D7', alpha=0.6, 
                                 linestyle='--', label=f'FATO Quadrada (1.5xD = {lado_fato:.1f}m)')
        ax.add_patch(fato)

        lado_tlof = d_rotor_m
        tlof = patches.Rectangle((-lado_tlof/2, -lado_tlof/2), lado_tlof, lado_tlof, 
                                 linewidth=2.5, edgecolor='white', facecolor='#1A365D', alpha=0.98, 
                                 label=f'TLOF Azul/Branca (1xD = {d_rotor_m}m)')
        ax.add_patch(tlof)

        ax.text(0, 0, 'H', color='white', fontsize=26, fontweight='bold', ha='center', va='center')

        tri_dist = lado_tlof / 2.0
        tri_x = tri_dist * math.cos(rad_rumo)
        tri_y = tri_dist * math.sin(rad_rumo)
        triangle = patches.RegularPolygon((tri_x, tri_y), numVertices=3, radius=2.5, 
                                          orientation=rad_rumo - math.pi/2, color='#ECC94B')
        ax.add_patch(triangle)

        biruta_x, biruta_y = -35, 35
        ax.plot([biruta_x, biruta_x], [biruta_y, biruta_y + 8], color='black', linewidth=2)
        biruta_cone = patches.Polygon([[biruta_x, biruta_y + 8], [biruta_x + 8, biruta_y + 6], [biruta_x + 8, biruta_y + 4]], color='#DD6B20', label='Biruta')
        ax.add_patch(biruta_cone)
        ax.text(biruta_x + 4, biruta_y + 10, 'BIRUTA', fontsize=8, fontweight='bold', color='#1A365D', ha='center')

        ax.annotate('NV', xy=(-20, 45), xytext=(-20, 32),
                    arrowprops=dict(facecolor='blue', edgecolor='blue', shrink=0.05, width=2, headwidth=8),
                    fontsize=10, fontweight='bold', color='blue', ha='center')

        ax.annotate(f'NM ({decl}°)', xy=(20, 45), xytext=(20, 32),
                    arrowprops=dict(facecolor='red', edgecolor='red', shrink=0.05, width=2, headwidth=8),
                    fontsize=10, fontweight='bold', color='red', ha='center')

        rx = 48 * math.cos(rad_rumo)
        ry = 48 * math.sin(rad_rumo)
        ax.plot([0, rx], [0, ry], color='#2B6CB0', linestyle='-', linewidth=3, label=f'Eixo Aprox: {rumo_verdadeiro}°V / {rumo_mag}°M')

        plt.title(f"AEROSIGMA - PLANTA TÉCNICA DE HELIPONTO\nProjeto: {self.nome_projeto}", fontsize=12, fontweight='bold', pad=20)
        ax.legend(loc='lower left', fontsize=8)
        ax.grid(True, linestyle=':', alpha=0.6)

        info_text = (
            f" ESPECIFICAÇÕES TÉCNICAS DA INFRAESTRUTURA:\n"
            f" -------------------------------------------------------------------\n"
            f" Coordenadas do Centro : Lat {self.lat:.6f}° | Lon {self.lon:.6f}°\n"
            f" Altitude de Referência  : {self.alt_m} m (MSL)\n"
            f" Peso Máx. Aeronave (MTOW): {self.peso_kg:,.1f} kg\n"
            f" Aeronave Crítica (D)   : Diâmetro Rotor = {d_rotor_m} m\n"
            f" Declinação Magnética  : {decl}° W\n"
            f" Orientação Rumo       : {rumo_verdadeiro}° (Verdadeiro) -> {rumo_mag}° (Magnético)\n"
            f" Norma Reguladora      : RBAC 154 / ICA 63-19 (ANAC / DECEA)\n"
        )
        fig.text(0.12, 0.08, info_text, fontsize=9, bbox=dict(boxstyle="round,pad=0.5", facecolor="#EDF2F7", edgecolor="#CBD5E0"))

        plt.tight_layout()
        plt.subplots_adjust(bottom=0.31)

        with PdfPages(nome_arquivo_pdf) as pdf:
            pdf.savefig(fig)
        plt.close()

# Interface Web com Streamlit
st.sidebar.header("⚙️ Parâmetros do Heliponto")

# Botão de Geolocalização Integrado
st.sidebar.markdown("### 📍 GPS do Telemóvel")
loc = streamlit_geolocation()

# Valores padrão de fallback
lat_default = -23.550520
lon_default = -46.633308

if loc and loc.get('latitude') and loc.get('longitude'):
    lat_default = loc['latitude']
    lon_default = loc['longitude']
    st.sidebar.success("✅ GPS capturado com sucesso!")

nome_proj = st.sidebar.text_input("Nome do Projeto", "Heliponto de Campo", key="nome_projeto")
lat = st.sidebar.number_input("Latitude", value=float(lat_default), format="%.6f", key="lat_proj")
lon = st.sidebar.number_input("Longitude", value=float(lon_default), format="%.6f", key="lon_proj")
alt = st.sidebar.number_input("Altitude (metros)", value=760.0, key="alt_proj")
peso = st.sidebar.number_input("Peso Máximo da Aeronave (kg)", value=5400.0, key="peso_proj")

modelo = st.sidebar.selectbox("Modelo de Aeronave", [
    "Personalizado",
    "Robinson R66 (Rotor 10.0m)",
    "AS350 Esquilo (Rotor 10.7m)",
    "EC135 / H135 (Rotor 10.2m)",
    "AW139 (Rotor 13.8m)",
    "Sikorsky S-92 (Rotor 17.7m)"
], key="modelo_aeronave")

if "R66" in modelo:
    d_rotor = 10.0
elif "Esquilo" in modelo:
    d_rotor = 10.7
elif "EC135" in modelo:
    d_rotor = 10.2
elif "AW139" in modelo:
    d_rotor = 13.8
elif "S-92" in modelo:
    d_rotor = 17.7
else:
    d_rotor = st.sidebar.number_input("Diâmetro do Rotor (m)", value=13.8, key="rotor_perso")

rumo = st.sidebar.slider("Rumo de Aproximação (°)", 0.0, 360.0, 140.0, key="rumo_aprox")

if st.button("🚀 Gerar Ficheiros do Heliponto", key="btn_gerar"):
    engine = AerosigmaEngine(lat, lon, alt, nome_projeto=nome_proj, peso_kg=peso)
    fato = engine.gerar_fato_tlof_quadrada(d_rotor)
    cone = engine.gerar_cone_aproximacao_3d(azimute_rampa_deg=rumo)
    
    nome_kml = f"{nome_proj.replace(' ', '_')}.kml"
    nome_pdf = f"Planta_Tecnica_{nome_proj.replace(' ', '_')}.pdf"

    engine.exportar_kml(nome_kml, fato, cone, nome_proj)
    engine.gerar_planta_pdf(nome_pdf, d_rotor, rumo)

    st.success("✅ Projeto gerado com sucesso!")

    with open(nome_pdf, "rb") as f:
        st.download_button("📄 Descarregar Planta em PDF", f, file_name=nome_pdf, mime="application/pdf", key="dl_pdf")

    with open(nome_kml, "rb") as f:
        st.download_button("🌍 Descarregar Ficheiro KML 3D", f, file_name=nome_kml, mime="application/vnd.google-earth.kml+xml", key="dl_kml")