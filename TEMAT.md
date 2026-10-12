# Propagacja opóźnień w sieci autobusowej Krakowa

**Symulacja zdarzeń dyskretnych z agentami-pojazdami i łańcuchami kursów, skalibrowana i zwalidowana na danych GTFS-Realtime ZTP**

---

## 1. CO: cel, system, pytania

### Problem

Autobusy miejskie rzadko jeżdżą dokładnie według rozkładu. Opóźnienie narasta wzdłuż trasy i w ciągu dnia, a zarządca (ZTP) ma kilka dźwigni: zapas czasowy na pętlach, przytrzymywanie na przystankach, priorytet dla autobusów, częstotliwość. Chcemy zbudować model, który pokaże, jak opóźnienie rozchodzi się w sieci, i sprawdzić, które interwencje najbardziej obniżają opóźnienie i jego rozrzut.

### System

Autobusy MPK Kraków realizujące kursy po współdzielonej sieci: kilkaset pojazdów, ok. 8-9 tys. kursów na dobę, setki przystanków. Pozycje pojazdów zapisujemy co 5 s (GTFS-Realtime) i z nich wyznaczamy czasy przyjazdu i odjazdu na przystankach. Mamy już pełne dane z kilku dni roboczych (ok. 150 tys. zdarzeń przystankowych na dzień), więc model powstaje od początku z myślą o kalibracji i walidacji na danych rzeczywistych.

### Dlaczego to system złożony

Złożoność systemu opiera się na dwóch interakcjach, które wstępna analiza danych potwierdziła, oraz na jednej hipotezie, którą testujemy.

- **Łańcuchy kursów (interakcja w czasie).** Pojazd obsługuje w ciągu dnia łańcuch ok. 18 kursów (`block_id` w GTFS), zwykle tam i z powrotem na jednej linii. Opóźnienie z końca kursu przechodzi na początek następnego, o ile zapas na pętli go nie pochłonie. Przenoszenie jest progowe: silne przy krótkim zapasie, a przy długim znika. Ponieważ łańcuchy zmieniają kierunek, opóźnienie z jednego kierunku linii trafia na drugi.
- **Zakłócenia wspólne (interakcja w przestrzeni).** Linie dzielą słupki i odcinki (np. linia 179 dzieli ok. połowy odcinków z liniami 169 i 174), więc zakłócenie na odcinku dotyka wszystkich linii, które go przejeżdżają. W danych są one wolne (utrzymują się kilkadziesiąt minut) i mają wyraźny efekt dzienny.
- **Fala na korytarzu (zjawisko emergentne).** Połączenie obu interakcji daje falę: zakłócenie opóźnia kilka linii, a przez pętle z krótkim zapasem opóźnienie przechodzi na kierunek powrotny i wraca na korytarz w kolejnym kursie. Pokazujemy, że tego efektu nie da się uzyskać z samego rozkładu jazdy z szumem, przez porównanie modelu pełnego z modelami bez łańcuchów i bez zakłóceń wspólnych.
- **Sprzężenie od odstępu (hipoteza do sprawdzenia).** Opóźniony autobus zabiera więcej pasażerów i stoi dłużej, a następny nadrabia, co daje klasyczne zbijanie się pojazdów. Wstępne dane go nie pokazują, więc model ma je jako przełączalny element ($\gamma$), bazowo wyłączony. Wynik ujemny jest wynikiem projektu.

### Pytania badawcze

1. Jak szybko i gdzie narasta opóźnienie i jego rozrzut, i ile z tego resetuje pętla?
2. Jaka część rozrzutu to zakłócenia wspólne, jaka przenoszenie przez łańcuchy kursów, a jaka zakłócenia indywidualne?
3. Czy istnieje sprzężenie od odstępu (tendencja do zbijania się)?
4. Które interwencje obniżają opóźnienie i rozrzut najbardziej i jakim kosztem?

### Ustalenia z wstępnej analizy danych

- Przenoszenie przez łańcuchy okazało się istotne, a nie słabe, więc zostaje rdzeniem modelu. Zależy od zapasu na pętli i to jest główny wątek scenariuszy.
- Zakłócenia wspólne modelujemy jako wolne, z efektem dnia, a nie jako krótkie szoki w oknach kilkunastu minut.
- Sprzężenie od odstępu przechodzi z "oczekiwanego zjawiska" do "testowanej hipotezy" (bazowo wyłączone).
- Scenariusze dzielimy na oparte na danych i warunkowe (sekcja 2).

---

## 2. JAK: metoda i model

### Metoda

Symulacja zdarzeń dyskretnych w SimPy. Każdy pojazd to agent (proces) realizujący łańcuch kursów obu kierunków linii. Zdarzenia: przyjazd na przystanek, odjazd, wjazd na odcinek, odjazd z pętli, zakłócenie. Wyniki zapisujemy w tym samym schemacie co dane obserwowane, żeby porównywać je jedną funkcją.

### Model

**Sieć:** graf, w którym wierzchołki to słupki, a krawędzie to odcinki z bazowym czasem przejazdu z rozkładu.

**Propagacja opóźnienia $\Delta$ wzdłuż kursu** (odcinek $s\to s+1$):

$$\Delta_{i,s+1}=\Delta_{i,s}+a_{p,s}+e_{d(i)}+u_{d(i),h(i,s),s}+\gamma\,(h_{i,s}-h^{\text{rozk}}_{s})+\eta_{i,s}$$

- $a_{p,s}$ to dryf zależny od okresu dnia i odcinka,
- $e_{d}$ to efekt dzienny wspólny dla całej sieci,
- $u_{d,h,s}$ to wolne zakłócenie wspólne dla kursów (także różnych linii) w oknie dzień $\times$ godzina na odcinku $s$,
- $\gamma\,(h-h^{\text{rozk}})$ to sprzężenie od odstępu. Przełączalne, bazowo $\gamma=0$, model działa też przy $\gamma>0$,
- $\eta_{i,s}$ to szum indywidualny o ciężkim ogonie z niezależnymi przyrostami na odcinkach.

**Łańcuch kursów i pętla.** Dla kolejnego kursu $i^{+}$ tego samego pojazdu ($L_i$ to zaplanowany postój na pętli, $\ell_{\min}$ minimalny postój, $\delta$ resztkowe spóźnienie odjazdu z rozkładu empirycznego):

$$\Delta^{\text{odj}}_{i^{+}}=\max\left(\Delta_{i,\text{koniec}}+\ell_{\min}-L_i,\ \delta_{i^{+}}\right)$$

Gdy zapas jest większy niż opóźnienie, jest ono pochłonięte, w przeciwnym razie przechodzi na następny kurs. Ponieważ łańcuchy zmieniają kierunek, opóźnienie z jednego kierunku linii trafia na drugi.

### Kalibracja

Parametry ($a$, $e_d$, wariancja i skala czasowa $u$, ogon $\eta$, $\delta$, $\ell_{\min}$) dopasowujemy metodą ABC lub optymalizacją (Optuna) do statystyk przyrostów opóźnienia, krzywej pochłaniania na pętli i korelacji kolejnych kursów. Analiza wrażliwości (Morris, Sobol) wskaże parametry istotne. Kalibrujemy na części dni roboczych, a pozostałe zostają do walidacji. $\gamma$ identyfikujemy z efektami stałymi okno $\times$ odcinek, osobno dla krótkich i długich odstępów, bo korelacja kolejnych autobusów miesza sprzężenie z zakłóceniami wspólnymi.

### Walidacja

Podział czasowy i przestrzenny, z przedziałami ufności z bootstrapem po kursach:

- **Dni poza próbą:** część dni roboczych odkładamy i nie używamy do kalibracji. Walidujemy w dwóch wariantach: ze znanym efektem dziennym (czy struktura modelu się przenosi) i z efektem dziennym wylosowanym z rozkładu oszacowanego na dniach kalibracyjnych (czy model pokrywa także dni nietypowe).
- **Linie spoza kalibracji** (sekcja 4).
- **Weekendy** jako dodatkowy reżim.

| Wynika z konstrukcji (nie jest walidacją) | Nietrywialne testy |
|---|---|
| dodatni dryf | krzywa pochłaniania opóźnienia na pętli w funkcji zapasu, na dniach i liniach spoza kalibracji |
| liniowy wzrost wariancji przy niezależnych przyrostach | rozrzut błędu odstępu wzdłuż trasy i wzór dobowy (szczyty kontra pora poza szczytem) |
| | korelacje kolejnych kursów i kolejnych autobusów |
| | korelacje między liniami na wspólnych odcinkach |
| | ogony rozkładów (KS), RMSE czasów przejazdu odcinków |
| | wariant $\gamma=0$ kontra $\gamma>0$ |
| | ablacje: model bez łańcuchów kursów, bez zakłóceń wspólnych, bez efektu dziennego |

Modele odniesienia, które model musi pobić: sam rozkład jazdy, autoregresja opóźnienia wzdłuż trasy, empiryczny rozkład opóźnień po (linia, odcinek, godzina).

### Scenariusze "co by było, gdyby"

**Oparte na danych (główne):**

| Scenariusz | Wskaźnik |
|---|---|
| Dłuższy lub krótszy zapas czasowy na pętli | pochłonięte opóźnienie, rozrzut wzdłuż trasy |
| Zakłócenie na korytarzu | macierz kontagionu, czas powrotu do normy |
| Zmiana częstotliwości | rozrzut, czas oczekiwania |

**Warunkowe (wielkość efektu jest założeniem):**

| Scenariusz | Wskaźnik |
|---|---|
| Przytrzymywanie na przystankach (do rozkładu lub wg odstępu) | oczekiwany czas oczekiwania pasażera, czas przejazdu |
| Priorytet lub pas dla autobusów | opóźnienie, nachylenie rozrzutu |

Każdy scenariusz w kilkudziesięciu replikacjach z przedziałami ufności. Scenariusze warunkowe opisujemy jawnie jako warunkowe i pokazujemy wrażliwość na założoną wielkość efektu.

---

## 3. CZYM: dane, narzędzia, wizualizacja

### Dane

- **GTFS statyczny (ZTP):** kursy, przystanki, godziny, geometria tras, kalendarz oraz `block_id` (łańcuchy kursów pojazdu).
- **GTFS-Realtime (ZTP):** pozycje pojazdów i prognozy. ZTP nie udostępnia historii, więc zbieramy dane sami od 4.10 (pozycje co 5 s, prognozy co 30 s).
- **Z danych wyznaczamy:** zdarzenia przystankowe (przyjazd, odjazd, opóźnienie), łańcuchy kursów, fakty stylizowane do kalibracji i walidacji.
- **Wersje rozkładu jazdy:** sprawdzamy, czy rozkład zmieniał się w trakcie zbierania danych, i liczymy każdy dzień z właściwą wersją.
- **Geoportal:** budynki i ulice do wizualizacji 3D.

### Narzędzia

Python (uv), SimPy (symulacja), pandas, pyarrow, geopandas (dane), SALib (wrażliwość), Optuna lub ABC (kalibracja), matplotlib i Plotly (wykresy), pydeck (3D), Unity (3D, interaktywne scenariusze).

### Wizualizacja

- **Podstawowa:** mapa sieci z autobusami (kolor wg opóźnienia), diagram Mareya rzeczywisty obok symulowanego, mapa cieplna kontagionu, krzywa pochłaniania na pętli.
- **3D, wariant lekki:** pydeck (deck.gl), kolumny nad przystankami o wysokości proporcjonalnej do opóźnienia, animacja tras.
- **3D w Unity:** symulacja zostaje w Pythonie, a Unity wyświetla wyeksportowane wyniki. Plan: Kraków 3D z budynkami OSM i autobusami na trasach, rzeczywistość obok symulacji z synchronizowanym czasem, replay dnia roboczego w przyspieszonym czasie, a w dalszej kolejności interaktywne scenariusze.

---

## 4. Zakres

**MVP:**
- **Pilot:** linia 179 (oba kierunki, bo łańcuchy zmieniają kierunek), ok. 5 tys. zdarzeń na dzień roboczy.
- **Korytarz:** linie 169 i 174 (każda dzieli ok. połowy skierowanych odcinków z 179), rozszerzony o 173 i 144 (ok. 36% wspólnych odcinków) oraz 124 (ok. 32%).
- **Linie walidacyjne spoza kalibracji:** 194, 494 i 139 (9-13% wspólnych odcinków z 179), oraz 138 i 123 (brak wspólnych odcinków, dużo zdarzeń) jako walidacja zewnętrzna. Linia 704 jako przypadek porównawczy.
- model z łańcuchami kursów, wolnymi zakłóceniami wspólnymi z efektem dziennym, regułą pętli i przełączalnym sprzężeniem $\gamma$,
- kalibracja na dniach roboczych, walidacja na dniach poza próbą i liniach spoza kalibracji, ablacje,
- trzy scenariusze oparte na danych i dwa warunkowe,
- wizualizacja podstawowa i 3D w wariancie lekkim.

**Zaawansowany, jeśli wystarczy czasu:**
- bardziej rozbudowana sieć krakowska z parametrami zbiorczymi i walidacją na wielkościach zagregowanych,
- wizualizacja 3D w Unity (budynki, replay, rzeczywistość obok symulacji, interaktywne scenariusze).

---

## 5. Ograniczenia i ryzyka

- **Skromniejsza emergencja.** Jeśli sprzężenie od odstępu się nie potwierdzi, złożoność opiera się na łańcuchach kursów i zakłóceniach wspólnych. Wynik ujemny przedstawiamy jako ustalenie z danych, a wartość dodaną modelu pokazują ablacje.
- Sprzężenie od odstępu może być niezidentyfikowalne, bo szum pomiaru zaniża jego estymatę. Wynik interpretujemy ostrożnie.
- Krótkie zapasy na pętli występują głównie na nielicznych liniach (np. 704), więc sprawdzamy, czy wynik o przenoszeniu nie jest napędzany przez jedną linię.
- Efekty interwencji w scenariuszach warunkowych są założeniami, więc wyniki są warunkowe. Najlepiej obronione są scenariusze oparte na danych.
- Unity wymaga dodatkowej pracy, więc jeśli nie uda się go zrobić, zostaje wariant lekki w pydeck.