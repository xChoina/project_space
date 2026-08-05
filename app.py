#odpal .streamlit run app.py
import streamlit as st
import plotly.graph_objects as go
import numpy as np
import requests
import pandas as pd
import sqlite3
import json

from skyfield.api import load, wgs84, Star
from skyfield.data import hipparcos
from skyfield import almanac
from PIL import Image, ImageEnhance
from io import BytesIO


st.set_page_config(page_title="CosmoApp", layout="wide")
st.title("Kosmo")
hide_streamlit_style = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;600&display=swap');
    html,body,[class*="css"]{
        font-family: 'Space Grotesk', sans-serif;
    }
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    .js-plotly-plot{
        border-radius: 10px;
        overflow: hidden;
    }
    </style>
    """
st.markdown(hide_streamlit_style,unsafe_allow_html=True)
@st.cache_data
def pobierz_dane_z_bazy():
    conn = sqlite3.connect('kosmos.db')

    df_planety = pd.read_sql_query("SELECT * FROM Planety", conn, index_col='nazwa')
    df_gwiazdy = pd.read_sql_query("SELECT * FROM Gwiazdy", conn, index_col='hip_id')
    df_konst = pd.read_sql_query("SELECT * FROM Konstelacje ORDER BY nazwa, kolejnosc", conn)
    df_ksiezyce = pd.read_sql_query("SELECT * FROM Ksiezyce", conn, index_col='nazwa')
    conn.close()
    kolory = df_planety['kolor'].to_dict()
    rozmiary = df_planety['rozmiar'].to_dict()
    okresy = df_planety['okres'].to_dict()
    nazwy_gwiazd = df_gwiazdy['nazwa'].to_dict()

    konstelacje = {}
    for nazwa, grupa in df_konst.groupby('nazwa'):
        konstelacje[nazwa] = grupa['hip_id'].tolist()

    return kolory, rozmiary, okresy, nazwy_gwiazd, konstelacje, df_ksiezyce, df_planety

kolor_planet, rozmiar_planet, okres_planet, nazwy_gwiazd, konstelacje, ksiezyce, df_planety = pobierz_dane_z_bazy()
#wyszukanie lokalizacji
st.sidebar.header("Twoja lokalizacja")
wpisane_miasto = st.sidebar.text_input("Wpisz miasto:", "Warszawa")
@st.cache_data(ttl=86400)
def pobierz_współrzędne(miasto):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={miasto}&count=1&language=pl&format=json"
    try:
        dane = requests.get(url).json()
        if "results" in dane:
            lat = dane["results"][0]["latitude"]
            lon = dane["results"][0]["longitude"]
            znaleziona_nazwa = dane["results"][0]["name"]
            return lat, lon,znaleziona_nazwa
    except:
        pass
    return 52.1482, 21.0380, "Warszawa"
lat, lon , nazwa_miasta = pobierz_współrzędne(wpisane_miasto)
st.sidebar.success(f" {nazwa_miasta} (Lat: {lat:.2f}, Lon: {lon:.2f})")

@st.cache_data(ttl=1800)
def pobierz_zachmurzenie(lat,lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=cloud_cover"
        odpowiedz = requests.get(url).json()
        return odpowiedz['current']['cloud_cover']
    except:
        return None
chmury = pobierz_zachmurzenie(lat, lon)



@st.cache_data
def zaladuj_gwiazdy():
    with load.open(hipparcos.URL) as f:
        df = hipparcos.load_dataframe(f)
        jasne_df = df[df['magnitude'] <= 3.5]
        return jasne_df
df_gwiazdy = zaladuj_gwiazdy()

@st.cache_resource
def zaladuj_dane():
    planets = load('de421.bsp')
    jupiter_system = load('jup365.bsp')
    ts = load.timescale()
    return planets, jupiter_system ,ts

planets, jupiter_system ,ts = zaladuj_dane()
sun = planets['sun']
earth = planets['earth']
t=ts.now()
targets = {
    'Merkury': planets['mercury'],
    'Wenus': planets['venus'],
    'Ziemia': planets['earth'],
    'Mars': planets['mars'],
    'Jowisz': planets['jupiter barycenter'],
    'Saturn': planets['saturn barycenter'],
    'Uran': planets['uranus barycenter'],
    'Neptun': planets['neptune barycenter'],
    'Pluton': planets['pluto barycenter']
}

def generuj_widok_planeta(nazwa_planety,klucz_gl_ciala,system_danych, promien_km, paleta_kolrow, metryki, opis_tekst):
    all_ks = ksiezyce[ksiezyce['planeta'] == nazwa_planety]
    dom_ks = all_ks.head(4).index.tolist() if not all_ks.empty else []
    wybrane_ks = st.multiselect(
        f"Wybierz księżyce do wyświetlenia na modelu 3D:",
        options=all_ks.index.tolist(),default = dom_ks
    )
    ksiezyce_flr = all_ks.loc[wybrane_ks]
    fig = go.Figure()
    u = np.linspace(0,2*np.pi,60)
    v = np.linspace(0, np.pi, 60)
    x_pl = 1.0 * np.outer(np.cos(u),np.sin(v))
    y_pl = 1.0 * np.outer(np.sin(u),np.sin(v))
    z_pl = 1.0 * np.outer(np.ones(np.size(u)),np.cos(v))
    fig.add_trace(go.Surface(
                  x=x_pl,y=y_pl,z=z_pl, surfacecolor=z_pl, colorscale=paleta_kolrow,showscale=False,name=nazwa_planety, hoverinfo='name'
    ))
    dt=t.utc_datetime()
    planeta = system_danych[klucz_gl_ciala]

    if ksiezyce_flr.empty:
        max_zas = 5
    else:
        max_okr = ksiezyce_flr['okres'].abs().max()
        if max_okr > 600: max_zas = 350
        elif max_okr > 200: max_zas = 200
        else: max_zas = 35
    for name, wiersz in ksiezyce_flr.iterrows():
        klucz = wiersz['klucz_bsp']
        color = wiersz['kolor']
        period = wiersz['okres']

        try:
            moon = system_danych[klucz]
            poz_ksiezyca = planeta.at(t).observe(moon)
            x = (poz_ksiezyca.position.km[0] / promien_km)
            y = (poz_ksiezyca.position.km[1] / promien_km)
            z = (poz_ksiezyca.position.km[2] / promien_km)
            dystans_r = np.sqrt(x**2 + y**2 + z**2)
            dystans_km =dystans_r * promien_km


            kroki_czasowe = np.linspace(0, abs(period),200)
            t_orbit = ts.utc(dt.year,dt.month,dt.day, dt.hour + (kroki_czasowe * 24),dt.minute, dt.second)
            sciezka = planeta.at(t_orbit).observe(moon)
            ox = sciezka.position.km[0] / promien_km
            oy = sciezka.position.km[1] / promien_km
            oz = sciezka.position.km[2] / promien_km

            fig.add_trace(go.Scatter3d(
                x=ox,y=oy,z=oz,mode='lines',
                line=dict(color=color,width=2), opacity=0.35,
                showlegend=False,hoverinfo='skip'
            ))
            srednica = wiersz.get('srednica_km',3000)
            if pd.isna(srednica): srednica = 3000
            r_ks = (srednica/2) / promien_km
            u_k = np.linspace(0, 2* np.pi, 20)
            v_k = np.linspace(0, np.pi, 20)
            x_k = x + r_ks * np.outer(np.cos(u_k), np.sin(v_k))
            y_k = y + r_ks * np.outer(np.sin(u_k), np.sin(v_k))
            z_k = z + r_ks * np.outer(np.ones(np.size(u_k)), np.cos(v_k))

            fig.add_trace(go.Surface(
                x=x_k,y=y_k,z=z_k,
                surfacecolor=np.ones_like(z_k),
                colorscale=[[0,color], [1,color]],
                showscale=False,
                name=name,
                hovertemplate= f"<b>{name}</b><br>Odległość: {dystans_km:.1f} Km<extra></extra>"
            ))

            z_napis = z + (r_ks *1.5)
            fig.add_trace(go.Scatter3d(
                x=[x], y=[y], z=[z_napis],
                mode='text',
                text=[f"<b>{name}</b>"],
                textposition='top center',
                textfont=dict(color=color,size=10),
                showlegend=False,
                hoverinfo='skip'
            ))

        except KeyError:
            continue
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False, range=[-max_zas, max_zas]),
            yaxis=dict(visible=False, range=[-max_zas, max_zas]),
            zaxis=dict(visible=False, range=[-max_zas, max_zas]),
            bgcolor = 'rgba(0,0,0,0)', aspectmode='cube'
        ),
        paper_bgcolor = 'rgba(0,0,0,0)', plot_bgcolor = 'rgba(0,0,0,0)',
        font=dict(color='white'), margin=dict(l=0,r=0,b=0,t=0), height=600
    )
    st.plotly_chart(fig,use_container_width=True,config={'scrollZoom': True},key=f"wykres_3d_{nazwa_planety}")

    st.markdown("---")
    st.markdown(f"### Karta Fizyczna i Charakterystyka: {nazwa_planety}")
    with st.container(border=True):
        k1,k2,k3,k4 = st.columns(4)
        k1.metric(label=metryki[0][0], value=metryki[0][1])
        k2.metric(label=metryki[1][0], value=metryki[1][1])
        k3.metric(label=metryki[2][0], value=metryki[2][1])
        k4.metric(label=metryki[3][0], value=metryki[3][1])
    with st.expander(f"Zobacz szczegółowy raport o: {nazwa_planety}"):
        st.write(opis_tekst)
    st.markdown("---")
    st.markdown("### Dane Fizyczne")
    if not ksiezyce_flr.empty:
        df_do_pokaz = ksiezyce_flr.copy()
        df_do_pokaz = df_do_pokaz.rename(columns={
            'okres': 'Okres obiegu (dni)', 'srednica_km': 'Średnica (km)', 'Rok_odkrycia': 'Rok_odkrycia'
        })
        kolumny_wid = ['Okres obiegu (dni)']
        if 'Średnica (km)' in df_do_pokaz.columns: kolumny_wid.append('Średnica (km)')
        if 'Rok_odkrycia' in df_do_pokaz.columns: kolumny_wid.append('Rok odkrycia')
        st.dataframe(df_do_pokaz[kolumny_wid], use_container_width=True)
    else:
        st.warning("Zaznacz chociaż 1 księzyc")


tab_3d, tab_2d, tab_2d_gwiazdy, tab_kon ,tab_moon, tab_3d_jupiter = st.tabs(["Układ Słoneczny 3D", "Mapa nieba 2D", "Mapa nieba 2D - Gwiazdy", "Koniunkcja" ,"Księżycowa Strefa" ,"Układ Jowisza 3D"])
#3D_układ_słoneczny
with tab_3d:
    st.subheader("Trójwymiarowy model orbit")


    fig_3d = go.Figure()


    fig_3d.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0],
        mode='markers',
        marker=dict(size=rozmiar_planet['Słońce'],color=kolor_planet['Słońce']),
        name='Słońce', hovertemplate="<b>Słońce</b><extra></extra"
    ))
    for name,obj in targets.items():
        poz_od_sun = sun.at(t).observe(obj)
        x,y,z = poz_od_sun.position.au
        wektor_predkosci = poz_od_sun.velocity.km_per_s
        v_km_s = np.linalg.norm(wektor_predkosci)

        kolor = kolor_planet.get(name,'white')
        rozmiar = rozmiar_planet.get(name,5)
        fig_3d.add_trace(go.Scatter3d(
            x=[x],y=[y],z=[z],
            mode = 'markers',
            marker=dict(size=rozmiar,color=kolor),
            name=name,
            hovertemplate=f"<b>{name}</b><br>Pozycja X: {x:.2f} AU<br>Pozycja Y: {y:.2f} AU<br>Prędkość: {v_km_s:.2f} km/s<extra></extra>"
        ))
        dni_na_okr = okres_planet.get(name,365)
        dt = t.utc_datetime()

        orbit_start = -dni_na_okr
        orbit_end = 0
        if orbit_start < -45000:
            orbit_start = -45000
            orbit_end = 9000
        kroki_czasowe = np.linspace(orbit_start,orbit_end,150)
        t_orbit = ts.utc(dt.year,dt.month,dt.day + kroki_czasowe)
        sciezka = sun.at(t_orbit).observe(obj)
        ox,oy,oz = sciezka.position.au
        fig_3d.add_trace(go.Scatter3d(
            x=ox,y=oy,z=oz,
            mode = 'lines',
            line=dict(color=kolor,dash='dash', width=2),
            showlegend=False,
            hoverinfo='skip'
        ))

    fig_3d.update_layout(
    scene=dict(
        xaxis=dict(visible=False),yaxis=dict(visible=False),zaxis=dict(visible=False),
        bgcolor = 'black'
    ),
    paper_bgcolor = 'black', font=dict(color='white'), margin=dict(l=0,r=0,b=0,t=0)
)

    st.plotly_chart(fig_3d, use_container_width=True,config={'scrollZoom': True},key="wykres_3d")
czas_lokalny = t.utc_datetime().astimezone()
#2D_mapa_nieba
with tab_2d:
    st.subheader(f"Mapa nieba czasu lokalnego: ({czas_lokalny.strftime('%Y-%m-%d %H:%M')} UTC)")
    latidue = lat
    longitude = lon
    obs = earth + wgs84.latlon(latidue, longitude)
    fig_2d = go.Figure()
    widoczne = 0


    obiekty_2d = {k: v for k, v in targets.items() if k != 'Ziemia'}
    obiekty_2d['Słońce'] = planets['sun']
    obiekty_2d['Księżyc'] = planets['moon']
    dane_tabela = []

    for name, obj in obiekty_2d.items():
        astrometric = obs.at(t).observe(obj).apparent()
        alt, az, distance = astrometric.altaz()

        if alt.degrees > 0:
            widoczne += 1
            dist_au = distance.au
            dist_km = dist_au*149597871
            dane_tabela.append({
                "Obiekt": name,
                "Dystans(AU)": f"{dist_au:.4f} AU",
                "Dystans (km)": f"{dist_km:.0f} km"
            })
            fig_2d.add_trace(go.Scatterpolar(
                r=[90 - alt.degrees],
                theta=[az.degrees],
                mode='markers+text',
                text=[name],
                textposition='bottom center',
                marker=dict(size=12, color=kolor_planet.get(name, 'white')),
                name=name,
                hovertemplate=f'<b>{distance.au:.2f} AU<b><extra></extra>'
            ))

    st.markdown("---")
    kol1, kol2, kol3 = st.columns(3)
    kol1.metric(label="Obserwatorium", value=nazwa_miasta)
    kol2.metric(label="Zachmurzenie", value=f"{chmury}%" if chmury is not None else "Brak danych")
    kol3.metric(label="Widoczne obiekty", value=widoczne)
    st.markdown("---")

    fig_2d.update_layout(
        dragmode='pan',
        polar=dict(
            radialaxis=dict(range=[0,90], tickvals=[0, 30, 60, 90], ticktext=['90° (Zenit)', '60°', '30°', '0° (Horyzont)']),
            angularaxis=dict(direction="clockwise", rotation=90),
            bgcolor='rgba(0,0,0,0)'
        ),
        paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),height=600
    )
    if widoczne == 0:
        st.warning("Brak obiektów widocznych nad tobą")
    else:
        st.plotly_chart(fig_2d, use_container_width=True, key="wykres_2d")
        st.markdown("Odległość od Ziemi")
        df_odl = pd.DataFrame(dane_tabela)
        st.dataframe(df_odl,hide_index=True)

#MAPA2D_tylko_gwiazdy
with tab_2d_gwiazdy:
    st.subheader(f"Mapa nieba czasu lokalnego: ({czas_lokalny.strftime('%Y-%m-%d %H:%M')} UTC)")
    latidue = lat
    longitude = lon
    obs = earth + wgs84.latlon(latidue, longitude)
    fig_2d_gwiazdy = go.Figure()
    gwiazdy = Star.from_dataframe(df_gwiazdy)
    astro_gwiazdy = obs.at(t).observe(gwiazdy).apparent()
    alt_g, az_g, dist_g = astro_gwiazdy.altaz()

    maska_widocznosci = alt_g.degrees>0
    alt_widoczne = alt_g.degrees[maska_widocznosci]
    az_widoczne = az_g.degrees[maska_widocznosci]
    mag_widoczne = df_gwiazdy['magnitude'].values[maska_widocznosci]
    widoczne_hip = df_gwiazdy.index.values[maska_widocznosci]

    st.markdown("---")
    kol1, kol2, kol3 = st.columns(3)
    kol1.metric(label="Obserwatorium", value=nazwa_miasta)
    kol2.metric(label="Zachmurzenie", value=f"{chmury}%" if chmury is not None else "Brak danych")
    kol3.metric(label="Widoczne obiekty", value=len(widoczne_hip))
    st.markdown("---")

    pokaz_kon = st.toggle("Pokaż siatkę konstelacji na niebie", value=True)

    r_gwiazd = (90-alt_widoczne).tolist()
    theta_gwiazd = az_widoczne.tolist()

    rozmiary_gwiazd = np.maximum(1, (5 - mag_widoczne) * 3).tolist()
    teksty_gwiazd = [nazwy_gwiazd.get(hip,"") for hip in widoczne_hip]
    kolor_gwiazd = ['yellow' if tekst != "" else 'white' for tekst in teksty_gwiazd]
    pelne_info_gwiazd = []
    for i, hip in enumerate(widoczne_hip):
        nazwa_g = nazwy_gwiazd.get(hip,"Gwiazda nienazwana")
        jasnosc = mag_widoczne[i]
        pelne_info_gwiazd.append(
            f"<b>{nazwa_g}</b><br>"
            f"Numer katalogowy: HIP {hip}<br>"
            f"Jasność obserwowana: {jasnosc:.2f} mag"
        )
    fig_2d_gwiazdy.add_trace(go.Scatterpolar(
        r=r_gwiazd,
        theta = theta_gwiazd,
        mode = 'markers+text',
        text = teksty_gwiazd,
        textposition = 'top center',
        textfont = dict(color='#FFFFFF', size=8),
        marker=dict(size=rozmiary_gwiazd, color=kolor_gwiazd, opacity=0.8, line=dict(width=0.5, color='black')),
        name='Gwiazdy',
        hovertext=pelne_info_gwiazd,
        hovertemplate="%{hovertext}<extra></extra>"

    ))
    if pokaz_kon:
        for nazwa_kon, numer_hip in konstelacje.items():
            r_lin = []
            theta_lin = []
            r_avg = []
            theta_avg = []

            for hip in numer_hip:
                if hip in widoczne_hip:
                    idx = np.where(widoczne_hip == hip)[0][0]
                    r_lin.append(r_gwiazd[idx])
                    theta_lin.append(theta_gwiazd[idx])
                    r_avg.append(r_gwiazd[idx])
                    theta_avg.append(theta_gwiazd[idx])
                else:
                    r_lin.append(None)
                    theta_lin.append(None)
            if any(x is not None for  x in r_lin):
                fig_2d_gwiazdy.add_trace(go.Scatterpolar(
                    r = r_lin,
                    theta = theta_lin,
                    mode = 'lines',
                    line = dict(color='red',width=1.5,dash = 'dot'),
                    name = nazwa_kon,
                    hoverinfo='skip'
            ))
                if r_avg:
                    r_array = np.array(r_avg)
                    theta_rad = np.radians(theta_avg)
                    x_pkt = r_array * np.cos(theta_rad)
                    y_pkt = r_array * np.sin(theta_rad)
                    x_sr = np.mean(x_pkt)
                    y_sr = np.mean(y_pkt)
                    r_sr = np.sqrt(x_sr**2 + y_sr**2)
                    theta_sr = np.degrees(np.arctan2(y_sr,x_sr))
                    theta_sr = (theta_sr + 360) % 360
                    r_sr += 6
                    fig_2d_gwiazdy.add_trace(go.Scatterpolar(
                        r=[r_sr],
                        theta=[theta_sr],
                        mode='text',
                        text = [f"<b>{nazwa_kon}</b>"],
                        textfont=dict(color='lightblue',size=13),
                        showlegend=False,
                        hoverinfo='skip'
                    ))

    fig_2d_gwiazdy.update_layout(
        dragmode='pan',
        polar=dict(
            radialaxis=dict(range=[0, 90], tickvals=[0, 30, 60, 90],ticktext=['90° (Zenit)', '60°', '30°', '0° (Horyzont)']),
            angularaxis=dict(direction="clockwise", rotation=90),
            bgcolor='rgba(0,0,0,0)',
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), height=700
    )
    st.plotly_chart(fig_2d_gwiazdy,use_container_width=True, key="wykres_2d_gwiazdy")
    st.markdown("---")
    st.markdown("Status konstelacji na niebie")
    wid_zestaw = set(int(hip) for hip in widoczne_hip)
    wypisane_kon = set()
    licz_g = 0
    for nazwa_kon, numer_hip in konstelacje.items():
        czysta_nazwa = str(nazwa_kon).strip()
        czy_cala_wid = all(int(hip) in wid_zestaw for hip in numer_hip)
        if czy_cala_wid and czysta_nazwa not in wypisane_kon:
            sklad_gwiazd= []
            for hip in numer_hip:
                nazwa_g = nazwy_gwiazd.get(hip, f"HIP {hip}")
                sklad_gwiazd.append(f"**{nazwa_g}**")

            unikalne_g = list(dict.fromkeys(sklad_gwiazd))
            st.write(f"**{czysta_nazwa}**:")
            st.caption(", ".join(unikalne_g))
            wypisane_kon.add(czysta_nazwa)
            licz_g += 1

    if licz_g == 0:
        st.info("W tym momencie nie ma żadnej konstelacji z bazy")

with tab_kon:
    st.header("Koniunkcje kalendarz")
    st.write("System automatycznie skanuje przyszłe pozycje orbit")
    @st.cache_data(ttl=86400)
    def pobierz_najblizsze_koniunkcje():
        from skyfield.api import load
        import datetime
        import numpy as np
        ts = load.timescale()
        planets = load('de421.bsp')
        earth = planets['earth']
        obiekty = {
            "Księżyc": ('moon', planets['moon']),
            "Merkury": ('mercury barycenter', planets['mercury barycenter']),
            "Wenus": ('venus barycenter', planets['venus barycenter']),
            "Mars": ('mars barycenter', planets['mars barycenter']),
            "Jowisz": ('jupiter barycenter', planets['jupiter barycenter']),
            "Saturn": ('saturn barycenter', planets['saturn barycenter'])
        }
        nazwy = list(obiekty.keys())
        klucze = [v[0] for v in obiekty.values()]
        ciala = [v[1] for v in obiekty.values()]
        now_time = datetime.datetime.now(datetime.timezone.utc)
        wektor_dni = ts.from_datetimes([now_time + datetime.timedelta(days=i) for i in range(180)])

        znal = []
        for i in range(len(ciala)):
            for j in range(i+1, len(ciala)):
                c1 = ciala[i]
                c2 = ciala[j]
                obs = earth.at(wektor_dni)
                sep = obs.observe(c1).apparent().separation_from(obs.observe(c2).apparent()).degrees
                for k in range(1, len(sep)-1):
                    if sep[k]< sep[k-1] and sep[k] < sep[k+1] and sep[k] < 4.0:
                        dzien_kon = now_time + datetime.timedelta(days=k)
                        wektor_godzin = ts.from_datetimes([dzien_kon + datetime.timedelta(hours=h) for h in range(-24, 25)])
                        obs_dok = earth.at(wektor_godzin)
                        sep_godz = obs_dok.observe(c1).apparent().separation_from(obs_dok.observe(c2).apparent()).degrees
                        id_min = np.argmin(sep_godz)
                        dokl_data = dzien_kon + datetime.timedelta(hours=int(id_min - 24))
                        min_dys = sep_godz[id_min]

                        if dokl_data > now_time:
                            znal.append({
                                "Zjawisko": f"{nazwy[i]} oraz {nazwy[j]}",
                                "Klucz1": klucze[i],
                                "Klucz2": klucze[j],
                                'Data': dokl_data,
                                'Dystans': min_dys
                            })
        znal.sort(key=lambda x: x["Data"])
        return znal[:10]
    with st.spinner("Skanowanie orbit"):
        lista_koniun = pobierz_najblizsze_koniunkcje()
    if lista_koniun:
        obs_lokal = earth + wgs84.latlon(lat,lon)
        for kon in lista_koniun:
            # 1. Wyliczamy lokalne warunki widoczności
            t_zjawiska = ts.from_datetime(kon['Data'])

            c1_obj = planets[kon['Klucz1']]
            c2_obj = planets[kon['Klucz2']]

            # Pobieramy wysokość ciał i słońca
            alt1, _, _ = obs_lokal.at(t_zjawiska).observe(c1_obj).apparent().altaz()
            alt_sun, _, _ = obs_lokal.at(t_zjawiska).observe(sun).apparent().altaz()

            wysokosc_deg = alt1.degrees

            # 2. Oceniamy sens obserwacji
            if wysokosc_deg < 0:
                status_wid = "🔴 **Niewidoczne** (schowane pod horyzontem)"
            elif alt_sun.degrees > -5:
                status_wid = "🟠 **Bardzo trudne** (środek dnia lub jasny świt/zmierzch)"
            elif wysokosc_deg < 12:
                status_wid = "🟡 **Nisko na niebie** (potrzebny płaski horyzont np. łąka, pole)"
            else:
                status_wid = "🟢 **Świetne warunki** (ciemne niebo i odpowiednia wysokość)"

            # 3. Rysujemy piękny i użyteczny interfejs
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                col1.markdown(f"#### {kon['Zjawisko']}")

                # Informacja z poradnikiem dla obserwatora
                if kon['Dystans'] < 1.0:
                    col1.success(
                        f"Zbliżenie na {kon['Dystans']:.2f}°. Obydwa obiekty zmieszczą się obok siebie w jednym kadrze teleskopu!")
                else:
                    col1.info(
                        f"Zbliżenie na {kon['Dystans']:.2f}°. Super widok gołym okiem lub przez prostą lornetkę.")

                # Dodajemy wygenerowany z Twojego miasta status
                col1.caption(f"Widoczność z {nazwa_miasta}: {status_wid} (Wysokość: {wysokosc_deg:.0f}°)")

                czas_lok = kon['Data'].astimezone()

                col2.metric(
                    label="Data maksimum (Twój czas)",
                    value=czas_lok.strftime("%Y-%m-%d"),
                    delta=czas_lok.strftime("%H:%M"),
                    delta_color="off"
                )
                col3.metric(
                    label="Odległość",
                    value=f"{kon['Dystans']:.2f}°"
                )
        else:
            st.info("Brak w ciągu najbliższego pół roku")


with tab_moon:
    st.subheader("Moon")
    moon = planets['moon']
    prcnt_light = almanac.fraction_illuminated(planets, 'moon', t) * 100
    phase_degree = almanac.moon_phase(planets, t).degrees

    if phase_degree < 5 or phase_degree > 355:
        phase_name = "Nów 🌑"
    elif phase_degree < 85:
        phase_name = "Sierp rosnący 🌒"
    elif phase_degree < 95:
        phase_name = "Pierwsza kwadra 🌓"
    elif phase_degree < 175:
        phase_name = "Księżyc garbaty rosnący 🌔"
    elif phase_degree < 185:
        phase_name = "Pełnia 🌕"
    elif phase_degree < 265:
        phase_name = "Księżyc garbaty malejący 🌖"
    elif phase_degree < 275:
        phase_name = "Trzecia kwadra 🌗"
    else:
        phase_name = "Sierp malejący 🌘"

    odleglosc_km = earth.at(t).observe(moon).distance().km

    st.markdown("---")
    with st.container(border=True):
        st.markdown(f"**Dane na czas:** {czas_lokalny.strftime('%Y-%m-%d %H:%M')}")
        k1, k2, k3 = st.columns([4, 1, 2])
        k1.metric(label="Aktualna Faza", value=phase_name)
        k2.metric(label="Oświetlenie Tarczy", value=f"{prcnt_light:.1f}%")
        k3.metric(label="Odległość od Ziemi", value=f"{odleglosc_km:.0f}km")

    st.markdown("---")
    st.markdown("Struktura 3D")


    @st.cache_data
    def pobierz_texture_moon():
        try:
            from PIL import Image, ImageEnhance
            img = Image.open("2k_moon.jpg").convert('L')

            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.25)
            if hasattr(Image, 'Resampling'):
                img = img.resize((1024, 512), Image.Resampling.LANCZOS)
            else:
                img = img.resize((1024, 512), Image.ANTIALIAS)

            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            return np.array(img)
        except Exception as e:
            return None


    img_array = pobierz_texture_moon()
    fig_moon = go.Figure()
    r_moon = 1737

    # TYLKO JEDEN BLOK RYSOWANIA MODELU 3D
    if img_array is not None:
        H, W = img_array.shape
        theta_moon = np.linspace(0, 2 * np.pi, W)
        phi_moon = np.linspace(0.005, np.pi - 0.005, H)
        THETA, PHI = np.meshgrid(theta_moon, phi_moon)

        x_m = r_moon * np.sin(PHI) * np.cos(THETA)
        y_m = r_moon * np.sin(PHI) * np.sin(THETA)
        z_m = r_moon * np.cos(PHI)

        pokaz_faze = st.toggle("🌓 Pokaż rzeczywisty cień fazy", value=True)

        # Kopia do operacji matematycznych
        img_display = img_array.copy().astype(float)

        if pokaz_faze:
            theta_sun = 2 * np.pi - np.radians(phase_degree)
            x_sun = np.cos(theta_sun)
            y_sun = np.sin(theta_sun)

            # Prawo Lamberta - liczymy kąt padania światła dla każdego piksela
            nasw = (np.sin(PHI) * np.cos(THETA) * x_sun) + (np.sin(PHI) * np.sin(THETA) * y_sun)

            # Wygładzenie przejścia na linii terminatora
            nasw_ostr= np.clip(nasw*15, 0, 1)
            jasnosc = 0.15 + (0.85 * nasw_ostr)

            # Aplikujemy cień na teksturę
            img_display = img_display * jasnosc

        # Dodajemy model na scenę (światło wyłączone, bazujemy na jasności tekstury)
        fig_moon.add_trace(go.Surface(
            x=x_m, y=y_m, z=z_m,
            surfacecolor=img_display,
            colorscale='gray',
            cmin=0, cmax=255,
            showscale=False,
            lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0, roughness=1.0, fresnel=0.0)
        ))

    fig_moon.update_layout(
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            bgcolor='rgba(0,0,0,0)', aspectmode='data',
            camera=dict(eye=dict(x=-2.5, y=0.0, z=0.0),
                        up=dict(x=0, y=0, z=1))
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),
        margin=dict(l=0, r=0, t=0, b=0), height=550
    )

    st.plotly_chart(fig_moon, use_container_width=True, config={'scrollZoom': False})


with tab_3d_jupiter:
    st.subheader("Model 3D: JOWISZ")
    dane_jowisz = df_planety.loc['Jowisz']
    kolory_baza = json.loads(dane_jowisz['kolory_3d']) if pd.notna(dane_jowisz['kolory_3d']) else 'orange'

    metryki_baza =[
        ("Masa", dane_jowisz['masa']),
        ("Czas obrotu", dane_jowisz['czas_obrotu']),
        ("Średnia temp.", dane_jowisz['temp']),
        ("Wiatry", dane_jowisz['wiatry'])
    ]
    generuj_widok_planeta(
        nazwa_planety="Jowisz",
        klucz_gl_ciala="jupiter",
        system_danych=jupiter_system,
        promien_km=71492,
        paleta_kolrow=kolory_baza,
        metryki = metryki_baza,
        opis_tekst = dane_jowisz['opis']
    )