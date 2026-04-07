from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/about", response_class=HTMLResponse)
def about_page() -> str:
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
    }

    .back a {
      text-decoration: none;
      color: #2563eb;
    }
  </style>
</head>
<body>

<div class="container">
  <h1>About VerbBoard</h1>

  <div class="lang-toggle">
    <button onclick="setLang('en')" id="btn-en" class="active">🇺🇸 EN</button>
    <button onclick="setLang('ru')" id="btn-ru">🇷🇺 RU</button>
    <button onclick="setLang('es')" id="btn-es">🇪🇸 ES</button>
    <button onclick="setLang('he')" id="btn-he">🇮🇱 HE</button>
  </div>

  <!-- EN -->
  <div id="content-en" class="content active">
    <p><b>What this is</b><br/>
    Learn verbs through usage, not memorization.</p>

    <p><b>Verb order</b><br/>
    Verbs are roughly ordered by frequency and usefulness.</p>

    <p><b>Progress</b><br/>
    ★ = learned<br/>
    ✓ = seen<br/>
    Progress is saved in your browser.</p>

    <p><b>Missing verbs</b><br/>
    Type a verb — we track demand and add new ones over time.</p>
  </div>

  <!-- RU -->
  <div id="content-ru" class="content">
    <p><b>Что это</b><br/>
    Изучение глаголов через использование, а не заучивание.</p>

    <p><b>Порядок глаголов</b><br/>
    Глаголы примерно отсортированы по частоте и полезности.</p>

    <p><b>Прогресс</b><br/>
    ★ = запомнил<br/>
    ✓ = видел<br/>
    Прогресс сохраняется в браузере.</p>

    <p><b>Нет глагола</b><br/>
    Введите глагол — мы учитываем спрос и со временем добавляем новые.</p>
  </div>

  <!-- ES -->
  <div id="content-es" class="content">
    <p><b>Qué es</b><br/>
    Aprende verbos mediante uso, no memorización.</p>

    <p><b>Orden de los verbos</b><br/>
    Los verbos están ordenados aproximadamente por frecuencia y utilidad.</p>

    <p><b>Progreso</b><br/>
    ★ = aprendido<br/>
    ✓ = visto<br/>
    El progreso se guarda en tu navegador.</p>

    <p><b>Faltan verbos</b><br/>
    Escribe un verbo — registramos la demanda y añadimos más.</p>
  </div>

  <!-- HE -->
  <div id="content-he" class="content" dir="rtl">
    <p><b>מה זה</b><br/>
    לומדים פעלים דרך שימוש, לא שינון.</p>

    <p><b>סדר הפעלים</b><br/>
    הפעלים מסודרים בקירוב לפי תדירות ושימושיות.</p>

    <p><b>התקדמות</b><br/>
    ★ = נלמד<br/>
    ✓ = נראה<br/>
    ההתקדמות נשמרת בדפדפן.</p>

    <p><b>פועל חסר</b><br/>
    הקלידו פועל — אנחנו עוקבים אחרי הביקוש ומוסיפים בהמשך.</p>
  </div>

  <div class="back">
    <a href="/">← Back</a>
  </div>
</div>

<script>
function setLang(lang) {
  document.querySelectorAll('.content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.lang-toggle button').forEach(el => el.classList.remove('active'));

  document.getElementById('content-' + lang).classList.add('active');
  document.getElementById('btn-' + lang).classList.add('active');
}
</script>

</body>
</html>
"""
