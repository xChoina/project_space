#odpal streamlit run app.py
import streamlit as st
import plotly.graph_objects as go
import numpy as np
import requests
import pandas as pd
import sqlite3
from skyfield.api import load, wgs84, Star
from skyfield.data import hipparcos

st.title("Kosmo")
@st.cache_data
def pobierz_dane_z_bazy():
    conn = sqlite3.connect('kosmos.db')

    df_planety = pd.read_sql_query("SELECT * FROM Planety", conn, index_col='nazwa')
    df_gwiazdy = pd.read_sql_query("SELECT * FROM Gwiazdy", conn, index_col='hip_id')
    conn.close()
    kolory = df_planety['kolor'].to_dict()
    rozmiary = df_planety['rozmiar'].to_dict()
    okresy = df_planety['okres'].to_dict()
    nazwy_gwiazd = df_gwiazdy['nazwa'].to_dict()
    return kolory, rozmiary, okresy, nazwy_gwiazd

kolor_planet, rozmiar_planet, okres_planet, nazwy_gwiazd = pobierz_dane_z_bazy()
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
st.sidebar.header(f"Pogoda {nazwa_miasta}:")
if chmury is not None:
    st.sidebar.metric(label="Zachmurzenie", value=f"{chmury}%")
else:
    st.sidebar.write("Bezchmurne niebo")

@st.cache_data
def zaladuj_gwiazdy():
    with load.open(hipparcos.URL) as f:
        df = hipparcos.load_dataframe(f)
        jasne_df = df[df['magnitude'] <= 2.5]
        return jasne_df
df_gwiazdy = zaladuj_gwiazdy()

@st.cache_resource
def zaladuj_dane():
    planets = load('de421.bsp')
    ts = load.timescale()
    return planets, ts

planets,ts = zaladuj_dane()
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

tab_3d, tab_2d, tab_2d_gwiazdy = st.tabs(["Układ Słoneczny 3D", "Mapa nieba 2D", "Mapa nieba 2D - Gwiazdy"])
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

    st.plotly_chart(fig_3d, use_container_width=True,key="wykres_3d")
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

    for name, obj in obiekty_2d.items():
        astrometric = obs.at(t).observe(obj).apparent()
        alt, az, distance = astrometric.altaz()
        if alt.degrees > 0:
            widoczne += 1
            fig_2d.add_trace(go.Scatterpolar(
                r=[90-alt.degrees],
                theta=[az.degrees],
                mode='markers+text',
                text=[name],
                textposition='bottom center',
                marker=dict(size=12, color=kolor_planet.get(name, 'white')),
                name=name,
                hovertemplate=f'<b>{distance.au:.2f} AU<b><extra></extra>'
            ))
    fig_2d.update_layout(
        polar=dict(
            radialaxis=dict(range=[0,90], tickvals=[0, 30, 60, 90], ticktext=['90° (Zenit)', '60°', '30°', '0° (Horyzont)']),
            angularaxis=dict(direction="clockwise", rotation=90),
            bgcolor='black'
        ),
        paper_bgcolor='black',font=dict(color='white'),height=600
    )
    if widoczne == 0:
        st.warning("Brak obiektów widocznych nad tobą")
    else:
        st.plotly_chart(fig_2d, use_container_width=True, key="wykres_2d")

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

    r_gwiazd = (90-alt_widoczne).tolist()
    theta_gwiazd = az_widoczne.tolist()

    widoczne_hip = df_gwiazdy.index.values[maska_widocznosci]
    teksty_gwiazd = [nazwy_gwiazd.get(hip,"") for hip in widoczne_hip]

    kolor_gwiazda = ['yellow' if tekst != "" else 'white' for tekst in teksty_gwiazd]
    fig_2d_gwiazdy.add_trace(go.Scatterpolar(
        r=r_gwiazd,
        theta = theta_gwiazd,
        mode = 'markers+text',
        text = teksty_gwiazd,
        textposition = 'top center',
        textfont = dict(color='yellow', size=10),
        marker=dict(size=4, color=kolor_gwiazda,opacity=0.6),
        name='Gwiazdy',
        hoverinfo='text'

    ))

    fig_2d_gwiazdy.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, 90], tickvals=[0, 30, 60, 90],
                            ticktext=['90° (Zenit)', '60°', '30°', '0° (Horyzont)']),
            angularaxis=dict(direction="clockwise", rotation=90),
            bgcolor='black'
        ),
        paper_bgcolor='black', font=dict(color='white'), height=600
    )
    st.plotly_chart(fig_2d_gwiazdy,use_container_width=True, key="wykres_2d_gwiazdy")
