import math
import requests
import streamlit as st
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

# Configuração da Página Web
st.set_page_config(page_title="Aerosigma - Helipontos", page_icon="🚁", layout="centered")

st.title("🚁 AEROSIGMA Web")
st.subheader("Gerador Profissional de Heliponto (UTM, SGRC, Coordenadas & Rampa 12,5%)")
st.write("Planta técnica avançada com suporte a UTM, SGRC/SIRGAS2000, Decimais, GMS e Rampa 12,5%.")

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

    def gerar_geometria_tlof_e_marcas(self, tamanho_tlof_m):
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
        return pontos_tlof

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

    def exportar_kml(self, nome_ficheiro, pontos_fato, pontos_tlof, poligonos_cone, nome_proj):
        kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
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
    <Placemark>
      <name>Área de Segurança FATO</name>
      <styleUrl>#estiloFato</styleUrl>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
"""
        for p in pontos_fato:
            kml_content += f"              {p[1]},{p[0]},{p[2]}\n"

        kml_content += """            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>TLOF - Heliponto</name>
      <styleUrl>#estiloTlof</styleUrl>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
"""
        for p in pontos_tlof:
            kml_content += f"              {p[1]},{p[0]},{p[2]}\n"

        kml_content += """            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
"""

        for idx, quad in enumerate(poligonos_cone):
            kml_content += f"""    <Placemark>
      <name>Cone de Aproximação - Seção {idx+1} (Rampa 12,5%)</name>
      <Polygon>
        <altitudeMode>absolute</altitudeMode>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
"""
            for p in quad:
                kml_content += f"              {p[1]},{p[0]},{p[2]}\n"

            kml_content += """            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
"""

        kml_content += """  </Document>
</kml>"""

        with open(nome_ficheiro, "w", encoding="utf-8") as f:
            f.write(kml_content)

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

        def rot(x, y, ang_deg):
            rad = math.radians(ang_deg)
            c, s = math.cos(rad), math.sin(rad)
            return x * c - y * s, x * s + y * c

        r_tri = 5.0
        pts_tri_base = []
        for j in range(3):
            ang = j * (2 * math.pi / 3) + math.pi/2
            pts_tri_base.append((r_tri * math.cos(ang), r_tri * math.sin(ang)))
        pts_tri_base.append(pts_tri_base[0])

        pts_tri = []
        for px, py in pts_tri_base:
            rx, ry = rot(px, py, rumo_mag)
            pts_tri.append((rx, ry))

        for j in range(3):
            ax.plot([pts_tri[j][0], pts_tri[j+1][0]], [pts_tri[j][1], pts_tri[j+1][1]], 
                    color='white', linewidth=2.0, linestyle=(0, (5, 5)))

        hw, hh = 1.8, 3.0
        h_seg_esq = [(-hw/2, -hh/2), (-hw/2, hh/2)]
        h_seg_dir = [(hw/2, -hh/2), (hw/2, hh/2)]
        h_seg_meio = [(-hw/2, 0), (hw/2, 0)]

        def desenhar_segmento_tracejado(p1, p2, ang_deg):
            x1, y1 = rot(p1[0], p1[1], ang_deg)
            x2, y2 = rot(p2[0], p2[1], ang_deg)
            passos = 6
            for k in range(passos):
                t1 = k / passos
                t2 = min(1.0, (k + 0.6) / passos)
                xa = x1 + (x2 - x1) * t1
                ya = y1 + (y2 - y1) * t1
                xb = x1 + (x2 - x1) * t2
                yb = y1 + (y2 - y1) * t2
                ax.plot([xa, xb], [ya, yb], color='white', linewidth=2.0)

        desenhar_segmento_tracejado(h_seg_esq[0], h_seg_esq[1], rumo_mag)
        desenhar_segmento_tracejado(h_seg_dir[0], h_seg_dir[1], rumo_mag)
        desenhar_segmento_tracejado(h_seg_meio[0], h_seg_meio[1], rumo_mag)

        ax.text(-5.0, -3.5, f"{self.peso_kg/1000:.1f}t", color='white', fontsize=6.0, fontweight='bold', ha='center', va='center', rotation=180, bbox=dict(boxstyle="square,pad=0.15", facecolor="#2B6CB0", edgecolor="white"))
        ax.text(tamanho_tlof_m/2 - 4.5, tamanho_tlof_m/2 - 2.0, f"{int(tamanho_tlof_m)} m", color='white', fontsize=9, fontweight='bold', ha='center', va='center', rotation=180, bbox=dict(boxstyle="square,pad=0.2", facecolor="#1A365D", edgecolor="white"))

        ax.annotate('', xy=(-3.0, 5.0), xytext=(-3.0, 8.0), arrowprops=dict(arrowstyle="->", color="white", lw=2.5))
        ax.annotate('', xy=(-6.5, 5.0), xytext=(-6.5, 2.0), arrowprops=dict(arrowstyle="->", color="white", lw=2.5))

        biruta_x, biruta_y = -12.5, -12.5
        ax.plot([biruta_x, biruta_x], [biruta_y, biruta_y + 3.0], color='black', linewidth=1.5)
        biruta_cone = patches.Polygon([[biruta_x, biruta_y + 3.0], [biruta_x + 3.0, biruta_y + 2.2], [biruta_x + 3.0, biruta_y + 0.8]], color='#DD6B20')
        ax.add_patch(biruta_cone)
        ax.text(biruta_x + 1.5, biruta_y + 4.0, 'BIRUTA', fontsize=5, fontweight='bold', color='white', ha='center', bbox=dict(boxstyle="square,pad=0.15", facecolor="#1A365D", edgecolor="white"))

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
            f" Gradiente de Aproximação: 12,5% (1:8)\n"
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

if 'lat_val' not in st.session_state:
    st.session_state.lat_val = -25.233580
if 'lon_val' not in st.session_state:
    st.session_state.lon_val = -49.093974
if 'alt_val' not in st.session_state:
    st.session_state.alt_val = 928.0
if 'rumo_aprox' not in st.session_state:
    st.session_state.rumo_aprox = 140.0
if 'formato_coord' not in st.session_state:
    st.session_state.formato_coord = "Graus Decimais (°)"

st.sidebar.markdown("### 📍 Coordenadas e Localização")

formato_coord = st.sidebar.selectbox(
    "Formato de Coordenadas", 
    ["Graus Decimais (°)", "Graus, Minutos e Segundos (GMS)", "UTM (Universal Transverse Mercator)", "SGRC / SIRGAS2000"], 
    key="formato_coord"
)

if formato_coord == "Graus Decimais (°)":
    lat_input = st.sidebar.number_input("Latitude", value=float(st.session_state.lat_val), format="%.6f", key="lat_dec")
    lon_input = st.sidebar.number_input("Longitude", value=float(st.session_state.lon_val), format="%.6f", key="lon_dec")
    st.session_state.lat_val = lat_input
    st.session_state.lon_val = lon_input

elif formato_coord == "Graus, Minutos e Segundos (GMS)":
    st.sidebar.write("Insira os componentes GMS:")
    
    def dec_para_gms(val):
        neg = val < 0
        val = abs(val)
        deg = int(val)
        minuto = int((val - deg) * 60)
        seg = round(((val - deg) * 60 - minuto) * 60, 2)
        return deg, minuto, seg, neg

    d_lat, m_lat, s_lat, neg_lat = dec_para_gms(st.session_state.lat_val)
    d_lon, m_lon, s_lon, neg_lon = dec_para_gms(st.session_state.lon_val)

    col1, col2, col3 = st.sidebar.columns(3)
    g_lat = col1.number_input("Lat Graus", value=d_lat, step=1, key="g_lat")
    mi_lat = col2.number_input("Min", value=m_lat, step=1, key="mi_lat")
    s_lat_in = col3.number_input("Seg", value=float(s_lat), format="%.2f", key="s_lat")

    col4, col5, col6 = st.sidebar.columns(3)
    g_lon = col4.number_input("Lon Graus", value=d_lon, step=1, key="g_lon")
    mi_lon = col5.number_input("Min", value=m_lon, step=1, key="mi_lon")
    s_lon_in = col6.number_input("Seg", value=float(s_lon), format="%.2f", key="s_lon")

    lat_sinal = -1 if neg_lat else 1
    lon_sinal = -1 if neg_lon else 1
    st.session_state.lat_val = lat_sinal * (abs(g_lat) + mi_lat/60.0 + s_lat_in/3600.0)
    st.session_state.lon_val = lon_sinal * (abs(g_lon) + mi_lon/60.0 + s_lon_in/3600.0)

else:
    st.sidebar.write("Insira os dados UTM / SGRC (Metros):")
    easting = st.sidebar.number_input("Easting (X - metros)", value=675000.0, format="%.2f", key="utm_e")
    northing = st.sidebar.number_input("Northing (Y - metros)", value=7205000.0, format="%.2f", key="utm_n")
    fuso = st.sidebar.number_input("Fuso UTM (Ex: 22 ou 23)", value=22, step=1, key="utm_fuso")
    
    lat_aprox = -25.0 + (7205000.0 - northing) / 111000.0
    lon_aprox = -49.0 - (675000.0 - easting) / 100000.0
    st.session_state.lat_val = lat_aprox
    st.session_state.lon_val = lon_aprox
    st.sidebar.info(f"📍 Convertido p/ Decimais: Lat {lat_aprox:.5f}°, Lon {lon_aprox:.5f}°")

alt_input = st.sidebar.number_input("Altitude (metros MSL)", value=float(st.session_state.alt_val), format="%.1f", key="alt_field")
st.session_state.alt_val = alt_input

nome_proj = st.sidebar.text_input("Nome do Projeto", "Heliponto 20m - 5t", key="nome_projeto")

opcoes_peso = {
    "3 Toneladas (3.000 kg)": 3000.0,
    "5 Toneladas (5.000 kg)": 5000.0,
    "8 Toneladas (8.000 kg)": 8000.0,
    "12 Toneladas (12.000 kg)": 12000.0
}
escolha_peso_txt = st.sidebar.selectbox("Peso Máximo da Aeronave (MTOW)", list(opcoes_peso.keys()), index=1)
peso = opcoes_peso[escolha_peso_txt]

tamanho_tlof = st.sidebar.slider("Tamanho do Heliponto (TLOF - metros)", 10.0, 30.0, 20.0, 1.0, key="tamanho_tlof_slider")

rumo = st.sidebar.slider("Rumo de Aproximação (°)", 0.0, 360.0, step=1.0, key="rumo_aprox")

if st.button("🚀 Gerar Ficheiros do Heliponto", key="btn_gerar"):
    engine = AerosigmaEngine(st.session_state.lat_val, st.session_state.lon_val, st.session_state.alt_val, nome_projeto=nome_proj, peso_kg=peso)
    fato = engine.gerar_fato_tlof_personalizada(tamanho_tlof)
    tlof_pts = engine.gerar_geometria_tlof_e_marcas(tamanho_tlof)
    cone = engine.gerar_cone_aproximacao_3d(azimute_rampa_deg=rumo)
    
    nome_kml = f"{nome_proj.replace(' ', '_')}.kml"
    nome_pdf = f"Planta_Tecnica_{nome_proj.replace(' ', '_')}.pdf"

    engine.exportar_kml(nome_kml, fato, tlof_pts, cone, nome_proj)
    engine.gerar_planta_pdf(nome_pdf, tamanho_tlof, rumo)

    st.success("✅ Projeto gerado com sucesso!")

    with open(nome_pdf, "rb") as f:
        st.download_button("📄 Descarregar Planta em PDF", f, file_name=nome_pdf, mime="application/pdf", key="dl_pdf")

    with open(nome_kml, "rb") as f:
        st.download_button("🌍 Descarregar Ficheiro KML 3D", f, file_name=nome_kml, mime="application/vnd.google-earth.kml+xml", key="dl_kml")
