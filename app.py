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
    df_konst = pd.read_sql_query("SELECT * FROM Konstelacje ORDER BY nazwa, kolejnosc", conn)
    conn.close()
    kolory = df_planety['kolor'].to_dict()
    rozmiary = df_planety['rozmiar'].to_dict()
    okresy = df_planety['okres'].to_dict()
    nazwy_gwiazd = df_gwiazdy['nazwa'].to_dict()

    konstelacje = {}
    for nazwa, grupa in df_konst.groupby('nazwa'):
        konstelacje[nazwa] = grupa['hip_id'].tolist()

    return kolory, rozmiary, okresy, nazwy_gwiazd, konstelacje

kolor_planet, rozmiar_planet, okres_planet, nazwy_gwiazd, konstelacje = pobierz_dane_z_bazy()
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

st.sidebar.markdown("---")
pokaz_kon = st.sidebar.toggle("Pokaż linie konstelacji", value=True)

@st.cache_resource(ttl=3600)
def pobierz_iss():
    url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle'
    try:
        satel = load.tle_file(url)
        for sat in satel:
            if 'ISS' in sat.name:
                return sat
    except Exception as e:
        st.error(e)
    return None
iss = pobierz_iss()


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
    fig_2d.update_layout(
        dragmode='pan',
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
        textfont = dict(color='yellow', size=7),
        marker=dict(size=4, color=kolor_gwiazd, opacity=0.6),
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
    if iss is not None:
        roz = iss-(wgs84.latlon(latidue,longitude))
        topcentr = roz.at(t)
        alt_iss, az_iss, distance_iss = topcentr.altaz()
        if alt_iss.degrees < 0:
            fig_2d_gwiazdy.add_trace(go.Scatterpolar(
                r=[90-alt_iss.degrees],
                theta=[az_iss.degrees],
                mode='markers+text',
                text=["ISS"],
                textposition='top center',
                textfont = dict(color='cyan', size = 14),
                marker=dict(size=15, color='cyan', symbol='diamond'),
                name="ISS",
                hovertext =[
                    f"<b>Międzynarodowa Stacja Kosmiczna</b><br>"
                    f"Wysokość: {alt_iss.degrees:.1f}°<br>"
                    f"Dystans: {distance_iss.km:.0f} km"
                ],
                hovertemplate="%{hovertext}<extra></extra>"
            ))
    fig_2d_gwiazdy.update_layout(
        dragmode='pan',
        polar=dict(
            radialaxis=dict(range=[0, 90], tickvals=[0, 30, 60, 90],ticktext=['90° (Zenit)', '60°', '30°', '0° (Horyzont)']),
            angularaxis=dict(direction="clockwise", rotation=90),
            bgcolor='black',
        ),
        paper_bgcolor='black', font=dict(color='white'), height=600
    )
    st.plotly_chart(fig_2d_gwiazdy,use_container_width=True, key="wykres_2d_gwiazdy")
    st.markdown("---")
    st.markdown("Status konstelacji na niebie")
    for nazwa_kon, numer_hip in konstelacje.items():
        sklad_gwiazd = []
        widoczne_cale = True

        for hip in numer_hip:
            nazwa_g = nazwy_gwiazd.get(hip, f"HIP {hip}")
            if hip in widoczne_hip:
                sklad_gwiazd.append(f"**{nazwa_g}**")
            else:
                sklad_gwiazd.append(f"{nazwa_g}")
                widoczne_cale = False

        st.write(f"**{nazwa_kon}** składa się z gwiazd: ")
        st.caption(", ".join(sklad_gwiazd))
