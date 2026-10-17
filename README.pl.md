# PhotoCraft × ComfyUI: mostek

[English README](README.md). Interfejs okna jest po angielsku; poniżej nazwy przycisków są podane tak, jak widać je w oknie.

Generative Fill, poszerzanie obrazu (outpaint), obraz → obraz i tekst → obraz w **PhotoCrafcie**,
liczone lokalnie przez **ComfyUI**. Wynik trafia do dokumentu jako **nowa warstwa z maską z zaznaczenia**,
czyli tak jak w Photoshopie.

```
 PhotoCraft (--control 7878)          mostek (python -m pccomfy)                ComfyUI :8188
 ┌───────────────────────┐   JSON/TCP  ┌──────────────────────────┐  HTTP + WS  ┌─────────────┐
 │ zaznaczenie + warstwy │ ──────────► │ 1. kopia, PNG obrazu+maski│ ──────────► │ inpaint /   │
 │                       │             │ 2. wycinek + skalowanie   │             │ img2img /   │
 │ nowa warstwa z maską  │ ◄────────── │ 3. wklejenie (Paste Into) │ ◄────────── │ txt2img     │
 └───────────────────────┘             └──────────────────────────┘             └─────────────┘
                 ▲   pliki PNG wymieniane przez ~/.cache/pccomfy/exchange   ▲
```

**Dlaczego mostek, a nie „plugin”:** pluginy PhotoCrafta to moduły WebAssembly w sandboksie,
bez dostępu do sieci i plików, widzące tylko piksele jednej warstwy. Z ComfyUI nie da się z nich połączyć.
PhotoCraft ma za to kanał sterowania, przez który można wywołać każdą z ~900 komend aplikacji,
i z niego korzysta ten mostek. Etap 2 (natywnie w Rust) opisuję na końcu.

---

## 1. Instalacja (Arch)

```bash
sudo pacman -S --needed python-pillow python-numpy tk python-websocket-client
```

- `pacman -S`: instaluje pakiety z repozytoriów Archa.
- `--needed`: pomija pakiety, które już masz (bez przeinstalowywania).
- `python-pillow`: obsługa obrazów (PNG, skalowanie, maski).
- `python-numpy`: szybkie operacje na pikselach (wypełnianie pola przy poszerzaniu).
- `tk`: biblioteka okienek, z której korzysta wbudowany w Pythona `tkinter`. Bez niej nie ruszy GUI mostka.
- `python-websocket-client`: opcjonalny, daje pasek postępu „krok 12/25”. Bez niego mostek co pół sekundy pyta ComfyUI o stan.

Pobierz kod z GitHuba:

```bash
git clone https://github.com/Peszemeszek/photocraft-comfyui-bridge.git ~/photocraft-comfyui-bridge
chmod +x ~/photocraft-comfyui-bridge/photocraft-ai.sh
```

- `git clone <adres> <folder>`: pobiera repozytorium razem z historią do wskazanego folderu. Aktualizacja to później `git pull` w tym folderze.
- `chmod +x`: daje skryptowi prawo uruchamiania.

Albo rozpakuj paczkę `.tar.gz`, jeśli ją masz:

```bash
mkdir -p ~/photocraft-comfyui-bridge && tar -xzf "$(xdg-user-dir DOWNLOAD)/photocraft-comfy.tar.gz" -C ~/photocraft-comfyui-bridge --strip-components=1
```

- `mkdir -p`: tworzy folder (i brakujące foldery nadrzędne), a jeśli już istnieje, nie zgłasza błędu.
- `tar -xzf`: `-x` rozpakowuje, `-z` obsługuje kompresję gzip, `-f` wskazuje plik archiwum.
- `-C ~/photocraft-comfyui-bridge`: rozpakowuje do tego folderu.
- `$(xdg-user-dir DOWNLOAD)`: ścieżka do Twojego folderu pobranych (Downloads, Pobrane…), niezależnie od języka systemu.
- `--strip-components=1`: pomija główny folder z archiwum, żeby pliki nie wylądowały piętro niżej.
- `chmod +x`: nadaje skryptowi prawo wykonywania, żeby dało się go odpalić jak program.

Konfiguracja jest opcjonalna, bo domyślne wartości pasują do typowego układu:

```bash
mkdir -p ~/.config/pccomfy && cp ~/photocraft-comfyui-bridge/config.example.toml ~/.config/pccomfy/config.toml
```

- `cp źródło cel`: kopiuje przykładową konfigurację w miejsce, z którego czyta ją mostek. Potem możesz ją edytować.

## 2. ComfyUI z Krity

Masz już ComfyUI postawione przez wtyczkę **Krita AI Diffusion**, więc mostek może z niego korzystać.
Jeśli Krita jest włączona i jej serwer działa, ComfyUI odpowiada na `http://127.0.0.1:8188` i niczego nie trzeba robić.

Bez Krity serwer można uruchomić ręcznie. Wtyczka trzyma go zwykle w `~/.local/share/krita/ai_diffusion/server`:

```bash
ls ~/.local/share/krita/ai_diffusion/server
~/.local/share/krita/ai_diffusion/server/venv/bin/python ~/.local/share/krita/ai_diffusion/server/ComfyUI/main.py --port 8188
```

- `ls`: wypisuje zawartość folderu. Sprawdź, czy są w nim `ComfyUI` i `venv` (u Ciebie ścieżka może się trochę różnić).
- `…/venv/bin/python`: Python ze środowiska, które zainstalowała Krita, z torch i węzłami ComfyUI.
- `ComfyUI/main.py`: start serwera ComfyUI.
- `--port 8188`: port HTTP, ten sam, którego używa Krita i domyślnie mostek.

Nie uruchamiaj tego, gdy Krita ma już swój serwer, bo port będzie zajęty.

## 3. Start

```bash
~/photocraft-comfyui-bridge/photocraft-ai.sh
```

Skrypt uruchamia PhotoCraft, a gdy ten zacznie nasłuchiwać, otwiera okno mostka. W środku robi mniej więcej to:

```bash
photocraft --control 7878 \
  --control-token-file ~/.config/pccomfy/photocraft.token \
  --automation-read-root ~/.cache/pccomfy/exchange \
  --automation-write-root ~/.cache/pccomfy/exchange
```

- `--control 7878`: włącza kanał sterowania na `127.0.0.1:7878`. Działa tylko lokalnie, z sieci nie da się go użyć.
- `--control-token-file …`: plik z 256-bitowym tokenem. Jeśli go nie ma, PhotoCraft sam go tworzy (prawa `0600`, czyli dostęp tylko dla Ciebie). Mostek czyta z niego token, a bez tokena nic nie wykona.
- `--automation-read-root` / `--automation-write-root`: jedyny folder, z którego automatyzacja może czytać i do którego może pisać. Tamtędy idą PNG obrazu, maski i wyników. Reszta dysku jest dla kanału sterowania zablokowana.
- `\` na końcu linii: kontynuacja polecenia w następnej linii, tylko dla czytelności.

Skrypt przyjmuje też zmienne środowiskowe, na przykład:

```bash
PCC_NO_GUI=1 ~/photocraft-comfyui-bridge/photocraft-ai.sh zdjecie.psd
```

- `PCC_NO_GUI=1` przed poleceniem ustawia zmienną tylko dla tego jednego uruchomienia: startuje sam PhotoCraft, bez okna mostka.
- `zdjecie.psd`: pliki podane na końcu skrypt przekazuje do PhotoCrafta do otwarcia.
- `PCC_PORT=7900` zmienia port, a `PHOTOCRAFT=/ścieżka/do/binarki` wskazuje inną binarkę (np. AppImage).

Okno mostka można też otworzyć osobno, gdy PhotoCraft już działa z `--control`:

```bash
cd ~/photocraft-comfyui-bridge && python -m pccomfy check
cd ~/photocraft-comfyui-bridge && python -m pccomfy
```

- `cd`: przejście do folderu mostka (`python -m` szuka pakietu `pccomfy` w bieżącym folderze).
- `python -m pccomfy check`: test połączeń. Wypisuje stan PhotoCrafta, ComfyUI i listę checkpointów. Od tego zacznij, gdy coś nie działa.
- `python -m pccomfy`: okno mostka.

## 4. Używanie

1. W PhotoCrafcie otwórz obraz i **zaznacz** obszar (lasso, prostokąt, Quick Selection; miękkie krawędzie zaznaczenia są respektowane).
2. W oknie mostka wybierz tryb, wpisz prompt i naciśnij **Generate** (`Ctrl+Enter`, a `Esc` przerywa).
3. Wynik pojawia się jako warstwa `AI inpaint: … [seed]` z maską. Przy kilku wariantach widoczny jest pierwszy, resztę włączasz okiem w panelu warstw.
4. Zaznaczenie zostaje przywrócone, więc można od razu generować jeszcze raz.

**Layer mask** (w sekcji *Advanced*):
- *soft* (domyślnie): to ta sama rozrośnięta i rozmyta maska, którą dostał model, więc wynik wtapia się bez twardej krawędzi. Maskę można dalej malować pędzlem.
- *hard*: dokładnie Twoje zaznaczenie (Paste Into), przydatna przy precyzyjnych kształtach.
- *none*: cały wygenerowany wycinek razem z kontekstem.

| Tryb | Co robi | Zaznaczenie | Denoise |
|---|---|---|---|
| **Generative fill** | Generative Fill: dorysowuje lub usuwa w zaznaczeniu | wymagane | 1.0 = nowa treść, 0.5–0.7 = poprawka istniejącej |
| **Expand image** | Generative Expand: powiększa płótno o podane px i dorysowuje brzegi | tworzy samo | 1.0 |
| **Image → image** | przerabia cały obraz albo zaznaczony fragment według promptu | opcjonalne | 0.3–0.7 |
| **Text → image** | generuje od zera w zaznaczeniu albo na całe płótno | opcjonalne | n/d |

**Advanced:**
- **Base res.** (rozdzielczość bazowa): generacja ma pole około `N×N` pikseli. Małe zaznaczenie jest powiększane (max 2×), żeby model miał detal, a duże zmniejszane. Dla SD1.5 ustaw 512–768, dla SDXL i Flux 1024.
- **Context**: ile otoczenia widzi model. Więcej kontekstu daje lepsze dopasowanie, mniej daje więcej detalu w małym obszarze.
- **Mask grow / Mask blur**: maska wysyłana do modelu jest trochę większa i miększa niż Twoje zaznaczenie, żeby model nadpisał krawędź. Przy masce warstwy *soft* ta sama maska trafia do warstwy.
- **Overlap** (outpaint): o ile pikseli nowy fragment wchodzi na stary obraz, żeby szew się wtopił.

**Fooocus inpaint (SDXL, jak w Kricie).** Jeśli serwer ComfyUI ma węzły *comfyui-inpaint-nodes* i pliki
`fooocus_inpaint_head.pth` oraz `inpaint_v26.fooocus.patch` w `models/inpaint` (instalacja Krity to zapewnia),
mostek sam ich użyje przy *Generative fill* i *Expand image*. Łatka zamienia zwykły checkpoint SDXL (RealVisXL, Juggernaut…) w model do inpaintu,
co daje dużo lepsze wtapianie. Działa tylko z SDXL, więc dla modeli SD1.5 odznacz pole w *Advanced*.
`python -m pccomfy check` pokaże, czy łatka została znaleziona.

**Prompt i denoise, czyli dwie rzeczy, które robią największą różnicę:**
- Prompt opisuje, **co ma być w zaznaczeniu**, a nie polecenie. Lepiej napisać `head of a ginger tabby cat, orange fur, photo` niż „replace the head…”.
  Modele SD/SDXL nie rozumieją instrukcji.
- **Denoise 1.0** rysuje w zaznaczeniu coś zupełnie nowego: nowy obiekt w nowej pozie i rozmiarze, wypełniający całe zaznaczenie.
  **Denoise 0.6–0.8** zachowuje kształt, pozę i oświetlenie tego, co już tam jest, i zmienia wygląd. Do „przefarbuj kota na rudo” użyj 0.7.
- Zaznaczaj obiekt ciasno. Przy denoise 1.0 model wypełnia całe zaznaczenie, więc za duże zaznaczenie daje za dużą głowę.
- Rozdzielczość bazowa: SDXL ok. 1024, SD1.5 ok. 512–768. Większe wartości dają podwójne obiekty i papkę.

Gotowy workflow z łatką Fooocus do podejrzenia lub edycji w ComfyUI jest w `workflows/sdxl-fooocus-inpaint.json`.
Przeciągnij go do okna ComfyUI w przeglądarce, a jeśli go zmienisz, wyeksportuj przez *Export (API)* do `~/.config/pccomfy/workflows/`.

## 5. Własne workflow (Flux Fill, Qwen-Image-Edit, ControlNet…)

1. Zbuduj workflow w ComfyUI (`http://127.0.0.1:8188`) i sprawdź, że działa.
2. Ustaw **tytuły** węzłów (prawy klik → *Title*):
   - `pc:image`: LoadImage, do którego trafi wycinek obrazu,
   - `pc:mask`: LoadImage na maskę (biały = generuj); za nim np. `ImageToMask` (kanał red),
   - `pc:prompt` i `pc:negative`: węzły tekstu (pole `text`),
   - `pc:sampler`: dostanie `seed`/`noise_seed` i `denoise`,
   - `pc:latent` albo `pc:size`: dostanie `width`, `height` (i `batch_size`),
   - `pc:output`: PreviewImage/SaveImage z wynikiem.
3. Wyeksportuj go przez **Workflow → Export (API)** do `~/.config/pccomfy/workflows/nazwa.json`.
4. W oknie mostka kliknij **Refresh** i wybierz go z listy *Workflow*.

Model, kroki, CFG i sampler biorą się wtedy z pliku, bo to „przepis” konkretnego modelu, więc te pola w oknie są wyszarzone.
Przykład w `workflows/flux-fill.json` (Flux.1 Fill w fp8, na 16 GB VRAM się mieści). Nazwy plików modeli zmień na swoje:

```bash
cp ~/photocraft-comfyui-bridge/workflows/flux-fill.json ~/.config/pccomfy/workflows/
```

## 6. Z linii poleceń

```bash
cd ~/photocraft-comfyui-bridge
python -m pccomfy run inpaint -p "rudy kot śpiący na parapecie" --variants 3
python -m pccomfy run outpaint -p "góry o zachodzie słońca" --expand 0 0 512 0
python -m pccomfy run img2img -p "akwarela" --denoise 0.45 -m juggernautXL_v9.safetensors
python -m pccomfy run inpaint -w ~/.config/pccomfy/workflows/flux-fill.json -p "drewniany stół"
```

- `run <tryb>`: jedna generacja na aktywnym dokumencie PhotoCrafta.
- `-p`: prompt; `-n`: negatyw.
- `-m`: checkpoint; bez niego bierze pierwszy z listy.
- `--variants 3`: trzy warianty, każdy jako osobna warstwa.
- `--expand L T R B`: o ile px poszerzyć lewo/górę/prawo/dół (tylko outpaint).
- `--denoise`, `--steps`, `--cfg`, `--seed`, `--res`: parametry jak w oknie.
- `-w`: własny workflow.

To polecenie da się przypiąć do skrótu globalnego w KDE (Ustawienia → Skróty → Dodaj polecenie).

## 7. Ograniczenia etapu 1

- W trakcie operacji mostek tworzy na chwilę kopię dokumentu (karta `pccomfy-…`) i otwiera PNG z wynikiem, więc zobaczysz mignięcie kart.
  Nie przełączaj dokumentów i **nie zmieniaj zaznaczenia w czasie generowania**, bo wynik jest wklejany w zaznaczenie aktywne w chwili wklejania.
- Pliki wyników mogą trafić do *Otwórz ostatnie* w PhotoCrafcie.
- Każdy krok to osobny wpis w historii (Rozmiar płótna, Wklej do itd.). Cofasz `Ctrl+Z` jak zwykle.
- Dokumenty CMYK/Lab/16-bit: kopia jest eksportowana do PNG, a wynik wklejany jako RGB 8-bit i konwertowany przez PhotoCraft.
- PhotoCraft to wczesna alfa, a kanał sterowania zmienia się razem z nim. Jeśli po aktualizacji coś przestanie działać, `python -m pccomfy check` i komunikat błędu powiedzą, która komenda.

## 8. Testy

```bash
python tests/e2e_headless.py /usr/bin/photocraft-cli
```

- Uruchamia `photocraft-cli serve` (PhotoCraft bez okna) i atrapę ComfyUI, potem przechodzi wszystkie cztery tryby i sprawdza warstwy, maski, rozmiar płótna i sprzątanie plików.
- Ścieżkę do `photocraft-cli` sprawdzisz poleceniem `which photocraft-cli` (jeśli pakiet z AUR go zawiera).

## 9. Etap 2: natywnie w PhotoCrafcie (Rust)

Kiedy mostek się sprawdzi, kolejny krok to przeniesienie go do PhotoCrafta. Plan:

- nowy crate `crates/ai` z klientem ComfyUI (HTTP + WebSocket, `reqwest`/`tungstenite`) i tymi samymi grafami,
- komendy `edit.generativeFill`, `edit.generativeExpand` i `image.generate` w rejestrze komend, liczone jako zadania w tle (`jobs`), z jednym krokiem historii,
- pasek kontekstowy pod zaznaczeniem z polem promptu i miniaturami wariantów (jak „Contextual Task Bar” w Photoshopie) w `ui-egui`,
- ustawienia w Preferencjach: adres serwera, folder workflow, domyślny model.

Bez kopii dokumentu, bez plików PNG po drodze i bez migających kart. Gałąź „AI” (G15) jest u nich oficjalnie otwarta,
więc dobrze zrobiony PR z lokalnym ComfyUI ma szansę wejść do upstreamu.
