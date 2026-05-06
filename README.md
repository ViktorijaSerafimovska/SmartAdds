# SmartAdds

Веб апликација за пребарување огласи од Pazar3 и Reklama5. Огласите се собираат со scraper, се зачувуваат локално и се пребаруваат со комбинација на keyword и semantic search. AI (Ollama) ги анализира и сумаризира резултатите.

---

## Барања

- Python 3.10+
- Git
- [Ollama](https://ollama.com) — мора да биде инсталиран и да работи

---

## Инсталација

### 1. Клонирај го проектот

```bash
git clone https://github.com/ViktorijaSerafimovska/SmartAdds.git
cd SmartAdds
```

### 2. Креирај virtual environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Mac / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Инсталирај ги зависностите

```bash
pip install -r requirements.txt
```

### 4. Конфигурирај го Ollama

Копирај го `.env.example` во `.env`:

```bash
cp .env.example .env
```

Отвори го `.env` и постави го `OLLAMA_HOST`:

- Ако Ollama работи на истата машина (Linux / Mac): остави го стандардно (`127.0.0.1`)
- Ако користиш WSL на Windows: постави го на WSL gateway IP-то. Добиј го со:
  ```bash
  cat /etc/resolv.conf | grep nameserver
  ```
  Потоа во `.env`:
  ```
  OLLAMA_HOST=172.31.x.x
  ```

Преземи го моделот (само еднаш):

```bash
ollama pull llama3.1
```

### 5. Собери огласи

```bash
python scraper/run_scraper.py
```

### 6. Стартувај го серверот

```bash
python -m uvicorn app.main:app --port 9000
```

> **Прво стартување:** серверот ќе изгради semantic search индекс за сите огласи. Ова трае ~2 минути. Следните стартувања се моментални (индексот е кеширан).

### 7. Отвори во browser

```
http://127.0.0.1:9000
```

---

## Освежување на огласи

За да ги обновиш огласите со нови податоци повторно стартувај го scraperот:

```bash
python scraper/run_scraper.py
```

После тоа рестартирај го серверот — semantic индексот ќе се изгради повторно автоматски.

---

## Пребарување

- **Кратки прашања** (`iphone 11`, `BMW`) — користи keyword search
- **Реченици** (`baram stan vo skopje centar do 500 evra`) — користи semantic search
- **Follow-up** (`спореди ги`, `кој е најевтин`) — AI анализа врз претходните резултати

Пилулата горе десно покажува кој режим е активен. При прво стартување, додека semantic индексот се гради, пилулата ќе покаже "loading" — keyword пребарувањето работи веднаш.
