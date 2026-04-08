SmartAdds е веб апликација за пребарување огласи од повеќе извори (Pazar3 и Reklama5). Огласите се собираат со scraper, се зачувуваат локално и потоа се пребаруваат според клучни зборови за да се добијат точни и релевантни резултати со директни линкови.

Потребно

За да се стартува проектот потребно е да имате инсталирано:

Python 3.10 или понов
Git
Инсталација и стартување
Симнете го проектот:
git clone https://github.com/ViktorijaSerafimovska/SmartAdds.git
cd SafeNet
Креирајте virtual environment:

Windows:

python -m venv .venv
.venv\Scripts\activate

Mac / Linux:

python3 -m venv .venv
source .venv/bin/activate
Инсталирајте ги потребните библиотеки:
pip install fastapi uvicorn requests beautifulsoup4 pydantic
Пуштете scraper за да се соберат огласите:
python scraper/run_scraper.py
Пуштете го backend серверот:
python -m uvicorn app.main:app --reload --port 9000
Отворете во browser:
http://127.0.0.1:9000
