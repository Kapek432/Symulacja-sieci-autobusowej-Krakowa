# Dane miasta: NMT i ortofotomapa dla Unity

Komenda `fetch-geoportal` pobiera fragmenty danych z oficjalnych uslug WCS GUGiK. NMT dostarcza wysokosci terenu, ortofotomapa kolor podloza. Dane zapisujemy lokalnie; skrypt nie importuje ich jeszcze do Unity.

## Instalacja i pierwszy test

Wymagane Python 3.14 i `uv`, jak dla reszty projektu. Grupa **geodata** dodaje Rasterio (obsluga GeoTIFF/GDAL) i certyfikaty CA `certifi`. Nie trzeba instalowac osobno QGIS ani GDAL. Pobieranie weryfikuje certyfikaty HTTPS.

Przyklad sprawdzony na fragmencie **200 x 200 m przy Rynku Glownym**:

```bash
uv run --group geodata fetch-geoportal \
  --bbox 566967 244147 567167 244347 \
  --out data/geoportal/rasters/rynek
```

`--bbox` to **xmin ymin xmax ymax w EPSG:2180**, metry, w kolejnosci **x=easting, y=northing**. Nie wpisujemy tu dlugosci/szerokosci geograficznej ani wspolrzednych lokalnych Unity. W programie GIS trzeba przeliczyc granice wybranego obszaru do EPSG:2180 i zachowac te kolejnosc osi. Komenda wyrownuje granice na zewnatrz do wspolnej siatki wybranych warstw.

Opcje:

```bash
# Plan i sprawdzenie limitow, bez sieci i zapisu
uv run fetch-geoportal --bbox 566967 244147 567167 244347 --dry-run

# Tylko NMT; domyslnie pobierane sa obie warstwy
uv run --group geodata fetch-geoportal \
  --bbox 566967 244147 567167 244347 --layers nmt \
  --out data/geoportal/rasters/rynek_nmt

# Ponowienie identycznej komendy korzysta z poprawnego cache.
# --overwrite wymusza pobranie od nowa.
```

Kazdy obszar trzymaj w osobnym `--out`. Pliki nazywaja sie `nmt_0000.tif`, `ortho_0000.tif` itd. Jesli zmienisz obszar lub parametry, stary cache nie zostanie uznany za zgodny; wybierz nowy katalog lub swiadomie uzyj `--overwrite`. Unikaj rownoleglego uruchamiania dwoch procesow w tym samym katalogu.

## Format, kontrola i wznowienie

- Obie warstwy wychodza jako GeoTIFF w **EPSG:2180**. NMT to jeden kanal wysokosci w metrach, ortofotomapa co najmniej trzy kanaly obrazu.
- NMT pobieramy jako **AAIGrid z warstwy `DTM_PL-EVRF2007-NH`** i konwertujemy na GeoTIFF. Naglowek AAIGrid nie ma CRS; przypisujemy EPSG:2180 zgodnie z zadanym `RESPONSE_CRS`. Wysokosci sa w **PL-EVRF2007-NH**. To nie jest wizualizacja cieniowania WMS.
- Domyslna rozdzielczosc wyjsciowa: **NMT 1 m**, **ortofotomapa 0,5 m/piksel**. Jest to rozdzielczosc zamowionego rastra, nie deklaracja rozdzielczosci zrodlowych zdjec.
- Walidujemy rozmiar, granice, CRS, kanaly i obecnosc skonczonych wartosci. Plik z samym NoData jest odrzucany. Przy czesciowym pokryciu zachowujemy maske brakow i zapisujemy procent poprawnych danych.
- Kazdy TIFF ma plik `.json`: pelny URL zapytania, uklad wysokosciowy NMT, czas pobrania UTC, parametry rastra, zakres wartosci, udzial danych, rozmiar i SHA-256.
- Pusta odpowiedz, XML zamiast rastra, blad HTTPS/HTTP i przerwany transfer sa ponawiane. Nieudana proba nie publikuje pliku wynikowego i nie niszczy poprzedniego TIFF-a.
- Zgodny cache jest sprawdzany po parametrach i SHA-256. Po przerwaniu uruchom te sama komende; uszkodzony/niekompletny cache wymaga `--overwrite`. Publikacja TIFF-a i JSON-a to dwa kolejne zastapienia plikow; przerwanie pomiedzy nimi zostanie wykryte przy nastepnym sprawdzeniu cache.

Definicje warstw i limity znajduja sie w sekcji `geoportal` pliku `configs/config.yaml`: kafelek 500 m, maksymalnie 100 kafelkow na obszar, 4 mln pikseli i 64 MiB odpowiedzi na kafelek/warstwe, timeout 45 s, 3 proby z opoznieniem 1 s i 2 s. Wiekszy obszar dzielimy na regiony albo swiadomie zmieniamy limity (`--config` pozwala wskazac inny pelny plik konfiguracji). Pobieranie jest sekwencyjne.

**Czas pobrania nie jest data wykonania zdjec/pomiarow.** Serwisy publikuja mozaiki, ktore moga sie aktualizowac. Zachowujemy lokalny snapshot i sumy kontrolne. Dobor konkretnych rocznikow przez skorowidze WFS pozostaje osobnym zadaniem.

## Zrodla i dalsze kroki

- [Oficjalna lista uslug WCS](https://www.geoportal.gov.pl/pl/usluga/uslugi-pobierania-wcs/).
- [NMT: zakres, uklady wysokosciowe i sposoby pobierania](https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/).
- [Ortofotomapa: uslugi i dane do pobrania](https://www.geoportal.gov.pl/pl/dane/ortofotomapa-orto/).

Budynki LoD1/LoD2 sa juz lokalnie w `data/geoportal/`; ten skrypt ich nie pobiera. Nastepne zadania to import NMT jako terenu Unity, ortofotomapy jako tekstury, konwersja budynkow GML i dopasowanie wszystkich warstw do wspolnego lokalnego ukladu autobusow. Przed polaczeniem wysokosci budynkow i NMT sprawdzamy ich uklady wysokosciowe; wysokosc bezwzgledna nie moze stac sie bezposrednio lokalnym `y` autobusu.

Dane i metadane w `data/` sa ignorowane przez Git. Do repo trafiaja kod, konfiguracja, testy i dokumentacja.

Testy bez internetu:

```bash
uv run --group geodata pytest tests/ingest/test_geoportal.py
```
