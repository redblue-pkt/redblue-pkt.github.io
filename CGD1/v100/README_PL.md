# CGD1 V10.0 — streaming BLE i Home Assistant

Baza: dostarczony CGD1 v99r8, nie starszy stan GitHuba. Obie części są zaimplementowane: firmware z odbiorem live do RAM oraz nowa integracja `cgd1_speaker` z encją `media_player` klasy speaker. GitHub nie został zmieniony.

## Instalacja

1. Wgraj `CGD1_v100.bin` za pomocą dołączonego TelinkMiFlasher.html. Flasher wskazuje ten sam plik w katalogu CGD1. Nie dodano banera wersji ani diagnostyki podświetlenia.
2. Rozpakuj `cgd1_speaker_1.0.0.tar.gz` do katalogu konfiguracji HA: ma powstać `/config/custom_components/cgd1_speaker/`. Uruchom HA ponownie. Integrację przygotowano do API HA 2026.10.2 (w tym probatio); nie deklaruje zgodności ze starszym HA.
3. Ustawienia → Urządzenia i usługi → Dodaj integrację → CGD1 Speaker. Nazwy `CGD_*` mają automatyczne wykrywanie; przy innej nazwie dodaj wykryty, dostępny do połączenia adres MAC ręcznie. Integracja korzysta z Bluetooth HA, także aktywnego proxy GATT. Przepustowość konkretnego proxy pozostaje do sprawdzenia.
4. Przed odtwarzaniem rozłącz flasher/Telink Manager i inne aplikacje korzystające z tego zegarka. Odbiornik audio wymaga jednego aktywnego połączenia BLE. FFmpeg musi być dostępny dla procesu HA; integracja korzysta z konfiguracji komponentu FFmpeg.
5. Dodaj standardową kartę media-control dla utworzonej encji. Obsługiwane: wybór audio z przeglądarki mediów HA, URL HTTP(S), TTS przez standardowe wywołanie odtwarzacza, STOP, głośność 0..5 i mute. Dla własnego TTS użyj np. akcji `tts.speak`, wskazując swój silnik TTS i utworzonego odtwarzacza jako `media_player_entity_id`.

Przykład (podmień encję i adres na własne):

```yaml
action: media_player.play_media
target:
  entity_id: media_player.cgd1_speaker
data:
  media_content_id: "http://ha.local:8123/local/alert.wav"
  media_content_type: music
```

## Audio i zachowanie

Host konwertuje audio podczas odczytu, a nie zapisuje całego pliku do zegarka. Domyślnie wybiera istniejący G.722, mono 16 kHz (8000 bajtów/s). Alternatywy zgodnie z maską firmware: A-law, mu-law, PCM8, PCM16, SBC mono 32 kbit/s, mSBC. Nie dodano nowych dekoderów. Firmware przyjmuje live także istniejące IMA ADPCM, ale adapter HA nie dodaje własnego kodera surowego legacy IMA. Opcjonalny AMR pozostaje dla plików; nie jest reklamowany jako live.

Wyjście CGD1 pozostaje 16 kHz, tak jak w v99r8. Tylko live wymaga 16 kHz; istniejąca ścieżka plików nadal ma dotychczasowe przeliczanie innych częstotliwości. Nie deklarujemy natywnego wyjścia 41 kHz.

Dodana kolejka zakodowanych danych: 2048 bajtów RAM; dotychczasowe bufory PCM i PWM zachowują rozmiary. Wstępne buforowanie: 512 bajtów zakodowanych danych i co najmniej 256 próbek wyjściowych. Dla krótkiego materiału END pozwala zacząć wcześniej. Jest to próg, nie gwarancja konkretnego opóźnienia.

START, DATA i obsługa live nie zapisują audio do SPI. Dekodery i PWM są współdzielone z odtwarzaniem dzwonków. Dane są dekodowane w głównej pętli, poza odbiorem GATT i przerwaniem audio. Brak danych daje neutralny sygnał, licznik niedoborów i stan buffering; 10 sekund bez nowych danych albo utrata połączenia kończą sesję. STOP opróżnia logicznie sesję. Zmiana głośności może potrzebować czasu na opróżnienie wcześniej przeskalowanej kolejki PWM (maksymalnie około 256 ms).

Stopa kończy streaming bez uruchamiania funkcji kończenia/drzemki alarmów. Lokalny alarm korzysta ze swojej dotychczasowej ścieżki rozłączenia BLE i przejmuje tor audio. STOP z HA ma token sesji i nie zatrzymuje alarmu, który przejął odtwarzanie. Podświetlenie nie jest włączane przez komendy streamingu.

Nie wystawiamy niedziałających funkcji pauzy, przewijania, kolejki, multiroom ani automatycznego przywracania muzyki po komunikacie. Nowe play_media przerywa poprzedni materiał. TTS i alerty działają jako nowy materiał. Integracja nie deklaruje obsługi ANNOUNCE z odtwarzaniem poprzedniego źródła po komunikacie.

## Usunięcie Telink SBC

Usunięto opcję TSBC z MakeCGD1, domyślnej konfiguracji, masek, dispatchera, enum i gałęzi dekodera. Usunięto Telink SBC, rozszerzenie `.tsbc` i jego parser z HTML. Zwykłe SBC i mSBC pozostały. Starsze nagranie w slocie TSBC nie zostanie odtworzone; w takim przypadku wgraj nagranie w pozostawionym formacie. Recovery zachowano jako niezmienione pliki historyczne, w tym rollback v99r8.

## Weryfikacja i granice

Kompilacja TC32 V10.0 zakończona bez ostrzeżeń. Toolchain: flyskywhy/tc32, gałąź linux, commit 8ec375bb95ef63b6d0a4b18008913c03e7928710. Ta sama kompilacja v99r8 dała binarnie identyczny obraz jak paczka bazowa.

Testy hosta:
- rzeczywiste funkcje C stream_command/stream_service: fragmenty PCM16, zawijanie kolejek, dokładne próbki PWM, END/drain, błędny token/sekwencja, timeout i rozłączenie; AddressSanitizer/UBSan (LeakSanitizer wyłączony z powodu środowiska);
- PCM8/PCM16/IMA/A-law/mu-law/G.722/SBC/mSBC: identyczne zdekodowane próbki v99r8 z pamięci, V10.0 z pamięci i V10.0 live;
- protokół Python: kredyty, przekroczenie 65535 pakietów i zawinięcie sekwencji, odrzucanie błędnych liczników/tokena, propagacja błędu DATA;
- rzeczywisty FFmpeg + lokalny HTTP + adapter HA z izolowanymi importami HA i symulowanym odbiornikiem BLE: G.722/SBC/mSBC, dokładne przesłane bajty, zakończenie, STOP, zmiana głośności;
- kontrola KNLT, długości i CRC firmware, składni JS/Python, nakładania patchy bez fuzz i wynikowego pliku patch-on-patch.

Nie wykonano testu w działającym HA ani na fizycznym CGD1. Przepustowość radia, opóźnienie, długie odtwarzanie i priorytet alarmu wymagają testu sprzętowego; symulacja tego nie potwierdza. Atrybut buffer_underruns udostępnia licznik braków próbek.

## Klient diagnostyczny bez HA

Po zainstalowaniu `bleak` i FFmpeg, z katalogu paczki:

```
python3 cgd1_live.py AA:BB:CC:DD:EE:FF nagranie.wav --volume 3
```

Ten klient przesyła G.722 na żywo, nie wgrywa nagrania do SPI. Wymaga rozłączenia HA/Telink Managera z tym zegarkiem.

## Pliki i patche

- `pvvx/`: kompletne źródła z SDK; budowanie `make -f MakeCGD1 TC32_PATH=/pełna/ścieżka/tc32/bin/`.
- `ha/`: nowa integracja; nie nadpisuje Telink Managera ani integracji pomiarów.
- `web/`: flasher ze wskazaniem V10.0 i bez Telink SBC.
- `cgd1_v99r8_to_v100.patch`: delta źródeł, `patch -p1` w źródłach v99r8.
- `cgd1_v100_on_clean_pvvx.patch`: pełny port na dokładnie tę czystą bazę PVVX, której dotyczył pełny patch v99r8; nie jest gwarancją zgodności z dzisiejszym upstream master.
- `cgd1_patchfile_v99r8_to_v100.patch`: zmiana zawartości starego pełnego patcha; po zastosowaniu otrzymuje się treść nowego pełnego patcha.
- `web_v99r8_to_v100.patch`: HTML i binarna zmiana obrazu, `git apply` w katalogu web.
- `web_v100_on_clean_pvvx.patch`: pełna zmiana web na czystą bazę używaną w poprzedniej paczce.
- `cgd1_speaker_1.0.0.patch`: dodanie nowej integracji przez `patch -p1` w konfiguracji HA.
- `tests/`: skrypty walidacji i minimalny zbiór bazowych źródeł dekoderów r8 do porównania.
- `recovery/`: historyczne recovery i rollback; nie są pełnym zrzutem konkretnego urządzenia.

SHA256SUMS obejmuje pliki paczki. Firmware V10.0 jest nowym obrazem, a nie przemianowanym v99r8. Wersjonowanie firmware wraca do zapisu PVVX bez przyrostka r.

## Odtworzenie paczki do publikacji

Archiwum pobrane z poprzedniej odpowiedzi było ucięte. Źródła odtworzono z v99r8 i zweryfikowanego patcha V10.0, a web z binarnego patcha. Sumy wszystkich plików src, SDK, HA, recovery, web oraz firmware są zgodne z oryginalnym manifestem V10.0. Usunięto uszkodzoną animację ble_browser.gif. Cztery skrypty test_*.py nie przetrwały w uciętym archiwum; raport wcześniejszej walidacji zachowano w VALIDATION.txt, a tests/baseline-r8 zawiera źródła porównawcze. Nie wykonano ponownie testów sprzętowych ani instalacji HA.
