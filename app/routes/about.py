from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

ABOUT_TITLES = {
    "en": "About VerbBoard",
    "ru": "О приложении VerbBoard",
    "es": "Sobre la VerbBoard",
    "he": "VerbBoard אודות",
}


@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request) -> str:
    lang = request.query_params.get("lang", "en")
    if lang not in {"en", "ru", "es", "he"}:
        lang = "en"
    return """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>About VerbBoard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body {
      font-family: system-ui, sans-serif;
      margin: 0;
      background: #f8fafc;
      color: #1f2937;
    }

    .container {
      max-width: 640px;
      margin: 40px auto;
      padding: 24px;
      background: white;
      border-radius: 16px;
      border: 1px solid #e5e7eb;
    }

    h1 {
      text-align: center;
      margin-bottom: 20px;
    }

    .lang-toggle {
      text-align: center;
      margin-bottom: 16px;
      font-size: 0.9rem;
    }

    .lang-toggle button {
      margin: 0 6px;
      padding: 4px 10px;
      border-radius: 6px;
      border: 1px solid #e5e7eb;
      background: #f1f5f9;
      cursor: pointer;
    }

    .lang-toggle button.active {
      background: #2563eb;
      color: white;
    }

    .content {
      display: none;
      font-size: 0.95rem;
      line-height: 1.5;
    }

    .content.active {
      display: block;
    }

    .content[dir="rtl"] {
      text-align: right;
    }

    .back {
      text-align: center;
      margin-top: 20px;
      display: flex;
      justify-content: center;
      gap: 20px;
    }

    .back a {
      text-decoration: none;
      color: #2563eb;
    }
  </style>
</head>
<body>

<div class="container">
  <h1>PAGE_TITLE</h1>

  <div class="lang-toggle">
    <button onclick="setLang('en')" id="btn-en" class="active">🇺🇸 EN</button>
    <button onclick="setLang('ru')" id="btn-ru">🇷🇺 RU</button>
    <button onclick="setLang('es')" id="btn-es">🇪🇸 ES</button>
    <button onclick="setLang('he')" id="btn-he">🇮🇱 HE</button>
  </div>

  <!-- EN -->
  <div id="content-en" class="content active">
    <p><b>What is VerbBoard?</b><br/>
    A focused tool for learning verbs in English, Spanish, Hebrew, and Russian.
    Each verb shows full conjugation with TTS audio for every form and example sentence.</p>

    <p><b>How it works</b><br/>
    Pick a language, pick a verb, study the forms. Play audio for any form or example.
    Switch between female and male voices. Mark verbs you know with ★.</p>

    <p><b>Verb order</b><br/>
    Verbs are ordered by frequency first, then by demand — verbs people searched for
    get added to the end of the list.</p>

    <p><b>Progress</b><br/>
    ★ = marked as known<br/>
    ✓ = seen<br/>
    Saved in your browser, no account needed.</p>

    <p><b>Feedback & verb requests</b><br/>
    Use the 💬 button on any page to leave feedback — feature ideas, bug reports, anything.<br/>
    To request a verb, just search for it on the home page. We track all searches and add
    the most requested ones.</p>
  </div>

  <!-- RU -->
  <div id="content-ru" class="content">
    <p><b>Что такое VerbBoard?</b><br/>
    Инструмент для изучения глаголов на английском, испанском, иврите и русском.
    Каждый глагол — полное спряжение с TTS-аудио для каждой формы и примера.</p>

    <p><b>Как это работает</b><br/>
    Выберите язык и глагол — изучайте формы. Прослушайте любую форму или пример.
    Переключайтесь между женским и мужским голосом. Отмечайте выученные глаголы звёздочкой ★.</p>

    <p><b>Порядок глаголов</b><br/>
    Сначала глаголы по частоте употребления, затем по спросу — глаголы, которые искали
    пользователи, добавляются в конец списка.</p>

    <p><b>Прогресс</b><br/>
    ★ = отмечен как выученный<br/>
    ✓ = уже просматривался<br/>
    Сохраняется в браузере, без регистрации.</p>

    <p><b>Отзывы и запросы глаголов</b><br/>
    Нажмите 💬 на любой странице, чтобы оставить отзыв — идеи, баги, всё что угодно.<br/>
    Чтобы запросить глагол, просто введите его на главной странице. Мы отслеживаем все
    запросы и добавляем самые популярные.</p>
  </div>

  <!-- ES -->
  <div id="content-es" class="content">
    <p><b>¿Qué es VerbBoard?</b><br/>
    Una herramienta para aprender verbos en inglés, español, hebreo y ruso.
    Cada verbo incluye conjugación completa con audio TTS para cada forma y ejemplo.</p>

    <p><b>Cómo funciona</b><br/>
    Elige un idioma y un verbo, estudia las formas. Escucha cualquier forma o ejemplo.
    Cambia entre voz femenina y masculina. Marca con ★ los verbos que ya dominas.</p>

    <p><b>Orden de los verbos</b><br/>
    Primero por frecuencia, luego por demanda — los verbos que la gente busca se añaden
    al final de la lista.</p>

    <p><b>Progreso</b><br/>
    ★ = marcado como aprendido<br/>
    ✓ = ya visto<br/>
    Se guarda en tu navegador, sin registro.</p>

    <p><b>Comentarios y solicitudes de verbos</b><br/>
    Usa el botón 💬 en cualquier página para dejar comentarios — ideas, errores, lo que sea.<br/>
    Para solicitar un verbo, simplemente búscalo en la página principal. Registramos todas
    las búsquedas y añadimos las más solicitadas.</p>
  </div>

  <!-- HE -->
  <div id="content-he" class="content" dir="rtl">
    <p><b>מה זה VerbBoard?</b><br/>
    כלי ללימוד פעלים באנגלית, ספרדית, עברית ורוסית.
    כל פועל מגיע עם נטייה מלאה ואודיו TTS לכל צורה ומשפט לדוגמה.</p>

    <p><b>איך זה עובד</b><br/>
    בחרו שפה ופועל ולמדו את הצורות. האזינו לכל צורה או משפט.
    עברו בין קול נשי לגברי. סמנו פעלים שלמדתם עם ★.</p>

    <p><b>סדר הפעלים</b><br/>
    קודם לפי תדירות, אחר כך לפי ביקוש — פעלים שאנשים חיפשו מתווספים לסוף הרשימה.</p>

    <p><b>התקדמות</b><br/>
    ★ = סומן כנלמד<br/>
    ✓ = כבר נראה<br/>
    נשמר בדפדפן, ללא צורך בהרשמה.</p>

    <p><b>משוב ובקשות לפעלים</b><br/>
    לחצו על 💬 בכל דף להשארת משוב — רעיונות, תקלות, כל דבר.<br/>
    כדי לבקש פועל, פשוט חפשו אותו בדף הבית. אנחנו עוקבים אחרי כל החיפושים
    ומוסיפים את הנפוצים ביותר.</p>
  </div>

  <div class="back">
    <a href="/">← Back</a>
    <a href="/feedback?page=about&return_to=/about">💬 Feedback</a>
  </div>
</div>

<script>
const ABOUT_TITLES = {
    en: 'About VerbBoard',
    ru: 'О приложении VerbBoard',
    es: 'Sobre la VerbBoard',
    he: 'VerbBoard אודות',
}
const _initLang = "INIT_LANG";
function setLang(lang) {
  document.querySelectorAll('.content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.lang-toggle button').forEach(el => el.classList.remove('active'));
  document.getElementById('content-' + lang).classList.add('active');
  document.getElementById('btn-' + lang).classList.add('active');
  document.querySelector('h1').textContent = ABOUT_TITLES[lang] || ABOUT_TITLES.en;
}
setLang(_initLang);
</script>

</body>
</html>
""".replace("INIT_LANG", lang).replace("PAGE_TITLE", ABOUT_TITLES[lang])
