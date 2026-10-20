# CGD1 v91: zakres, zgodność i sposoby aktualizacji

## Zidentyfikowane punkty odniesienia

- Firmware: źródła i binarka z dostarczonej paczki CGD1_v90_full.tar.gz.
- Binarka v90 na GitHub i w paczce jest identyczna: SHA-256 cbd85bfd1be84cd7e57f2adbea3d37e061de2d1a80f953b1ade5334b2b47d3d4.
- Repozytorium strony: redblue-pkt/redblue-pkt.github.io, master 8e2727b65653200306f2a85e93c8dcae311264d2.
- Czysta strona PVVX: pvvx/pvvx.github.io, commit 2b4467985c1095d76d82766a286f39d2ab65509a.
- Czysta baza firmware: odtworzona przez odwrócenie dostarczonego pełnego patcha v90. Paczka wejściowa nie zawierała historii Git pozwalającej wiarygodnie przypisać SHA upstream. Baza jest określona sumami plików w patch_bases.json.

## Co faktycznie zmienia v91

| Obszar | Wynik kontroli |
| --- | --- |
| Timer światła | Usunięty podgląd 5+1 wywołań co 100 ms. Podgląd i stopa korzystają z tego samego licznika czasu. Ponowne uruchomienie aktualizuje poziom i resetuje timer. |
| Zgodność z fabryką | v90 przeniosła fabryczny krótki podgląd BLE. Żądane pełne 8 s po zmianie suwaka jest świadomą zmianą zachowania względem fabrycznego podglądu, zgodną ze zgłoszeniem użytkownika. |
| Start | Po init_rtc/init_lcd i pierwszym pomiarze wykonywana jest synchronizacja konfiguracji, przekazanie czasu RTC oraz uruchomienie zapisanej jasności. Uwzględniany jest harmonogram nocy. |
| Alarmy | Wywołanie cgd1_app_time przy starcie ma również istniejący skutek oceny alarmów przy sekundzie 0 lub 1. Nie jest funkcją tylko od podświetlenia. Regresja jednoczesnego startu alarmu nie została sprawdzona na sprzęcie. |
| Stan w RAM | Usunięto dwa pola krótkiego podglądu. Przesuwa to kolejne pola struktury runtime; wymagane jest przebudowanie wszystkich zależnych modułów. MakeCGD1 ma już zależność obiektów od tego nagłówka. To nie jest migracja danych we flash. |
| EEPROM i SPI NOR | Struktura settings, wersja rekordu 2, identyfikatory 0x60/0x61/0x62, sektory rekordów, sloty dźwięku i migracja pozostają takie jak w v90. Dodano synchronizację RAM po udanym zapisie niezależną od dostępności zewnętrznej NOR. |
| PWM | Sekwencja rejestrów, polaryzacja i przeliczenie poziomów nie zostały zmienione względem v90. Wyjście 0 nadal wymusza GPIO PD3 w stanie niskim. Nie ma podstaw do deklaracji, że usunięto sprzętową przyczynę maksymalnej jasności. |
| Oszczędzanie energii | Światło nadal trzyma blokadę uśpienia; wyłączenie zwalnia blokadę. Zmiana okresu licznika na 1 s nie uruchamia osobnego przerwania sprzętowego. |
| BLE | Numery komend, długości pakietów i odpowiedzi bez zmian. 0x02 zapisuje jasność, 0x1a uruchamia podgląd, 0x1c zapisuje czas, 0x19 zapisuje harmonogram. Wersja aplikacji 0x91; prefiks odpowiedzi 0x90 jest identyfikatorem protokołu, a nie numerem tej wersji firmware. |
| Transfer | Wspólna blokada komend podczas uploadu/dumpu pozostaje. Podgląd nie uruchamia się podczas transferu. Nie zmieniono potwierdzeń stron, CRC, geometrii slotów ani dekoderów audio. |
| OTA i rozmiar | Nie zmieniono bootloadera ani mapy OTA. Obraz ma 114036 bajtów, poniżej limitu 0x20000; zapas 17036 bajtów. |
| MiFlasher | Istniejąca kolejność: odczyt ustawień → zapis jasności → odczyt kontrolny → podgląd. Naprawa timera jest po stronie firmware. Wariant strony zmienia tylko dwa wskazania binarki v90 → v91 i dodaje binarkę oraz test. |

## Granice potwierdzenia

Przyczyna świecenia na maksimum po baterii pozostaje niepotwierdzona. Synchronizacja przed startem usuwa niejednoznaczność kolejności, ale test startu zastępuje odczyt flash i sprzęt atrapami. Odrzucenie rekordu settings nadal ustawia domyślną jasność 10. Przy nieważnym RTC nie da się wiarygodnie wybrać pory dnia na podstawie rzeczywistej godziny.

Test czasu korzysta z modelu zegara. Rzeczywista pętla aplikacji wykonuje callback po przekroczeniu okresu i może opóźniać wyłączenie, zwłaszcza podczas operacji blokujących. Brak testu oscyloskopem, fizycznej baterii i fizycznego BLE uploadu.

## Wyniki weryfikacji

- Kompilacja TC32 i kontrola obrazu: PASS.
- Testy C: czas 1..30 s, 8 s, powtórzenie podglądu, stopa w trakcie podglądu, wyłączenie, nadpisanie czasu: PASS.
- Rzeczywista funkcja startowa z atrapami konfiguracji/RTC/sprzętu: PASS dla jasności dnia 2, nocy 3, zera i screen_off.
- MiFlasher: test kolejności komend suwaka oraz zapisu czasu: PASS. Test nie zastępuje urządzenia.
- Składnia JavaScript strony: PASS.
- Istniejący test zegara strony: PASS.
- Istniejący tests/cgd1-upload/layout.test.cjs: FAIL także na niezmienionym master; oczekuje starego tekstu i układu Test sound/Stop. Nie zmieniano tego testu ani interfejsu, aby ukryć wynik.
- Istniejący upload.test.cjs wymaga programu CGD1_HOST, którego nie ma w dostarczonej paczce źródeł. Testu transportu z tym hostem nie uruchomiono.

## Sposoby aktualizacji

| Punkt startowy | Metoda |
| --- | --- |
| Urządzenie z v90 | Wgrać CGD1_v91.bin przez istniejący MiFlasher, wybierając lokalny plik. Aktualizacja strony nie jest konieczna dla naprawy timera. |
| Czyste źródła PVVX zgodne z manifestem | cgd1_v91_on_clean_pvvx.patch, następnie pełna kompilacja. |
| Dokładne źródła v90 | cgd1_v90_to_v91.patch, następnie pełna kompilacja. |
| Bez własnych źródeł | Pełne pvvx/ z tej paczki oraz MakeCGD1 i narzędzia TC32. |
| Obecna strona użytkownika, wskazany commit | web_v90_to_v91.patch; zawiera aktualizację wskazań pliku i nową binarkę. |
| Czysta strona PVVX, wskazany commit | web_v91_on_clean_pvvx.patch; zawiera pełny interfejs CGD1 z obecnej strony, pomocnik zegara, binarkę v91 i testy. |
| GitHub | Osobna gałąź i draft PR z wariantem strony. Nie wymaga zastąpienia historii ani usuwania istniejących plików. |

Kontrola bazy źródeł bez zapisu: python3 apply_firmware_patch.py /sciezka/do/pvvx --base v90

Zastosowanie po kontroli: python3 apply_firmware_patch.py /sciezka/do/pvvx --base v90 --apply

Dla czystej bazy użyć --base clean. Skrypt porównuje SHA-256 i sprawdza patch z --fuzz=0; nie próbuje dopasowywać go do innej wersji. Dla patchy strony użyć git apply --check, a następnie git apply w katalogu głównym właściwego repozytorium.

Pełny patch strony na czysty PVVX i patch przyrostowy są wariantami alternatywnymi. Tak samo alternatywne są dwa patche firmware. Nie nakładać obu wariantów na ten sam katalog.
