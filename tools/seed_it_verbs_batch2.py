"""One-off seeding script: 40 more common Italian verbs (ranks 21-60),
session-authored (this content was written directly by the assistant in a
Claude Code session, not generated via `_call_claude`/the Anthropic API) to
avoid the cost of 40 live generation calls for a mechanically well-understood
batch of mostly-regular verbs. Written straight into the live `verbs`
Firestore collection, same as `tools/seed_it_verbs.py` (which seeded the
first 20, ranks 1-20, via the real API).

Conjugation forms below are built from a small set of regular-pattern
helpers (_ar/_acg/_aci/_er/_ir/_iisc) per Italian's standard conjugation
classes, with explicit overrides for the handful of irregular presente/
participio forms. Examples (5 Italian sentences + en/es/he/ru translations
each) are hand-written; where a verb's imperativo would be unnatural/
contrived in real Italian (sembrare), a different form is used instead of
forcing a bad "command" sentence -- same principle as
tools/fix_fr_pouvoir_imperative.py's handling of French's defective
imperative.

Usage:
    .venv/bin/python -m tools.seed_it_verbs_batch2
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.languages.it.plugin  # noqa: E402,F401  -- self-registers "it"
from core.storage.verb_document import build_search_extract_from_entry, build_verb_document  # noqa: E402
from core.storage.verb_repository import upsert_verb  # noqa: E402

LANGUAGE = "it"

_PERSONS = ["io", "tu", "lui", "noi", "voi", "loro"]

_AVERE = {"io": "ho", "tu": "hai", "lui": "ha", "noi": "abbiamo", "voi": "avete", "loro": "hanno"}
_ESSERE = {"io": "sono", "tu": "sei", "lui": "è", "noi": "siamo", "voi": "siete", "loro": "sono"}


def _pp(aux: str, participio: str) -> dict:
    auxd = _AVERE if aux == "avere" else _ESSERE
    if aux == "avere":
        return {p: f"{auxd[p]} {participio}" for p in _PERSONS}
    plur = participio[:-1] + "i" if participio.endswith("o") else participio + "i"
    return {
        "io": f"{auxd['io']} {participio}",
        "tu": f"{auxd['tu']} {participio}",
        "lui": f"{auxd['lui']} {participio}",
        "noi": f"{auxd['noi']} {plur}",
        "voi": f"{auxd['voi']} {plur}",
        "loro": f"{auxd['loro']} {plur}",
    }


def _ar(stem: str) -> dict:
    return {
        "presente": {
            "io": stem + "o",
            "tu": stem + "i",
            "lui": stem + "a",
            "noi": stem + "iamo",
            "voi": stem + "ate",
            "loro": stem + "ano",
        },
        "imperfetto": {
            "io": stem + "avo",
            "tu": stem + "avi",
            "lui": stem + "ava",
            "noi": stem + "avamo",
            "voi": stem + "avate",
            "loro": stem + "avano",
        },
        "futuro": {
            "io": stem + "erò",
            "tu": stem + "erai",
            "lui": stem + "erà",
            "noi": stem + "eremo",
            "voi": stem + "erete",
            "loro": stem + "eranno",
        },
        "imperativo": {"tu": stem + "a", "lei": stem + "i", "noi": stem + "iamo", "voi": stem + "ate"},
        "gerundio": stem + "ando",
    }


def _acg(stem: str) -> dict:
    d = _ar(stem)
    d["presente"]["tu"] = stem + "hi"
    d["presente"]["noi"] = stem + "hiamo"
    d["imperativo"]["lei"] = stem + "hi"
    d["imperativo"]["noi"] = stem + "hiamo"
    d["futuro"] = {
        "io": stem + "herò",
        "tu": stem + "herai",
        "lui": stem + "herà",
        "noi": stem + "heremo",
        "voi": stem + "herete",
        "loro": stem + "heranno",
    }
    return d


def _aci(stem: str) -> dict:
    base = stem[:-1]  # drop the stem's trailing "i" before endings starting with e/i
    return {
        "presente": {
            "io": stem + "o",
            "tu": base + "i",
            "lui": stem + "a",
            "noi": base + "iamo",
            "voi": stem + "ate",
            "loro": stem + "ano",
        },
        "imperfetto": {
            "io": stem + "avo",
            "tu": stem + "avi",
            "lui": stem + "ava",
            "noi": stem + "avamo",
            "voi": stem + "avate",
            "loro": stem + "avano",
        },
        "futuro": {
            "io": base + "erò",
            "tu": base + "erai",
            "lui": base + "erà",
            "noi": base + "eremo",
            "voi": base + "erete",
            "loro": base + "eranno",
        },
        "imperativo": {"tu": stem + "a", "lei": base + "i", "noi": base + "iamo", "voi": stem + "ate"},
        "gerundio": stem + "ando",
    }


def _er(stem: str) -> dict:
    return {
        "presente": {
            "io": stem + "o",
            "tu": stem + "i",
            "lui": stem + "e",
            "noi": stem + "iamo",
            "voi": stem + "ete",
            "loro": stem + "ono",
        },
        "imperfetto": {
            "io": stem + "evo",
            "tu": stem + "evi",
            "lui": stem + "eva",
            "noi": stem + "evamo",
            "voi": stem + "evate",
            "loro": stem + "evano",
        },
        "futuro": {
            "io": stem + "erò",
            "tu": stem + "erai",
            "lui": stem + "erà",
            "noi": stem + "eremo",
            "voi": stem + "erete",
            "loro": stem + "eranno",
        },
        "imperativo": {"tu": stem + "i", "lei": stem + "a", "noi": stem + "iamo", "voi": stem + "ete"},
        "gerundio": stem + "endo",
    }


def _ir(stem: str) -> dict:
    return {
        "presente": {
            "io": stem + "o",
            "tu": stem + "i",
            "lui": stem + "e",
            "noi": stem + "iamo",
            "voi": stem + "ite",
            "loro": stem + "ono",
        },
        "imperfetto": {
            "io": stem + "ivo",
            "tu": stem + "ivi",
            "lui": stem + "iva",
            "noi": stem + "ivamo",
            "voi": stem + "ivate",
            "loro": stem + "ivano",
        },
        "futuro": {
            "io": stem + "irò",
            "tu": stem + "irai",
            "lui": stem + "irà",
            "noi": stem + "iremo",
            "voi": stem + "irete",
            "loro": stem + "iranno",
        },
        "imperativo": {"tu": stem + "i", "lei": stem + "a", "noi": stem + "iamo", "voi": stem + "ite"},
        "gerundio": stem + "endo",
    }


def _iisc(stem: str) -> dict:
    d = _ir(stem)
    d["presente"] = {
        "io": stem + "isco",
        "tu": stem + "isci",
        "lui": stem + "isce",
        "noi": stem + "iamo",
        "voi": stem + "ite",
        "loro": stem + "iscono",
    }
    d["imperativo"] = {"tu": stem + "isci", "lei": stem + "isca", "noi": stem + "iamo", "voi": stem + "ite"}
    return d


_CLASS_FNS = {"AR": _ar, "ACG": _acg, "ACI": _aci, "ER": _er, "IR": _ir, "IISC": _iisc}


def _build_forms(entry: dict) -> dict:
    forms = _CLASS_FNS[entry["cls"]](entry["stem"])
    if "presente_override" in entry:
        forms["presente"] = entry["presente_override"]
    if "imperativo_override" in entry:
        forms["imperativo"] = entry["imperativo_override"]
    forms["participio"] = entry["participio"]
    forms["passato_prossimo"] = _pp(entry["aux"], entry["participio"])
    return forms


def _ex(dst: str, en: str, es: str, he: str, ru: str) -> dict:
    return {"dst": dst, "translations": {"en": en, "es": es, "he": he, "ru": ru}}


# VERBS is populated below by chunked edits.
VERBS: list[dict] = [
    {
        "lemma": "uscire",
        "cls": "IR",
        "stem": "usc",
        "aux": "essere",
        "participio": "uscito",
        "presente_override": {
            "io": "esco",
            "tu": "esci",
            "lui": "esce",
            "noi": "usciamo",
            "voi": "uscite",
            "loro": "escono",
        },
        "imperativo_override": {"tu": "esci", "lei": "esca", "noi": "usciamo", "voi": "uscite"},
        "translations": {"en": "to go out", "es": "salir", "ru": "выходить", "he": "לצאת"},
        "examples": [
            _ex(
                "Ogni sera esco con gli amici dopo cena.",
                "Every evening I go out with friends after dinner.",
                "Cada noche salgo con mis amigos después de cenar.",
                "כל ערב אני יוצא עם חברים אחרי ארוחת הערב.",
                "Каждый вечер я выхожу с друзьями после ужина.",
            ),
            _ex(
                "Ieri siamo usciti tardi dall'ufficio.",
                "Yesterday we left the office late.",
                "Ayer salimos tarde de la oficina.",
                "אתמול יצאנו מהמשרד מאוחר.",
                "Вчера мы поздно вышли из офиса.",
            ),
            _ex(
                "Da giovane uscivo spesso la sera.",
                "When I was young I often went out in the evening.",
                "De joven salía a menudo por la noche.",
                "כשהייתי צעיר הייתי יוצא הרבה בערבים.",
                "В молодости я часто выходил по вечерам.",
            ),
            _ex(
                "Domani uscirò presto per il lavoro.",
                "Tomorrow I will leave early for work.",
                "Mañana saldré temprano para el trabajo.",
                "מחר אצא מוקדם לעבודה.",
                "Завтра я выйду рано на работу.",
            ),
            _ex(
                "Esci subito, l'autobus sta arrivando!",
                "Go out now, the bus is coming!",
                "¡Sal ahora mismo, el autobús está llegando!",
                "צא מיד, האוטובוס מגיע!",
                "Выходи скорее, автобус уже едет!",
            ),
        ],
    },
    {
        "lemma": "entrare",
        "cls": "AR",
        "stem": "entr",
        "aux": "essere",
        "participio": "entrato",
        "translations": {"en": "to enter", "es": "entrar", "ru": "входить", "he": "להיכנס"},
        "examples": [
            _ex(
                "Entro in ufficio alle nove ogni mattina.",
                "I enter the office at nine every morning.",
                "Entro a la oficina a las nueve cada mañana.",
                "אני נכנס למשרד בתשע כל בוקר.",
                "Я вхожу в офис в девять каждое утро.",
            ),
            _ex(
                "Siamo entrati in casa proprio mentre pioveva.",
                "We entered the house right as it started raining.",
                "Entramos a casa justo cuando empezó a llover.",
                "נכנסנו הביתה בדיוק כשהתחיל לרדת גשם.",
                "Мы вошли в дом как раз когда начался дождь.",
            ),
            _ex(
                "Da bambina entravo sempre di nascosto in cucina.",
                "As a little girl I always used to sneak into the kitchen.",
                "De niña siempre entraba a escondidas en la cocina.",
                "כשהייתי ילדה תמיד הייתי נכנסת בחשאי למטבח.",
                "В детстве я всегда тайком заходила на кухню.",
            ),
            _ex(
                "Il treno entrerà in stazione tra pochi minuti.",
                "The train will enter the station in a few minutes.",
                "El tren entrará en la estación en pocos minutos.",
                "הרכבת תיכנס לתחנה בעוד כמה דקות.",
                "Поезд прибудет на станцию через несколько минут.",
            ),
            _ex(
                "Entra pure, la porta è aperta.",
                "Come on in, the door is open.",
                "Entra nomás, la puerta está abierta.",
                "תיכנס, הדלת פתוחה.",
                "Заходи, дверь открыта.",
            ),
        ],
    },
    {
        "lemma": "tornare",
        "cls": "AR",
        "stem": "torn",
        "aux": "essere",
        "participio": "tornato",
        "translations": {"en": "to return", "es": "volver", "ru": "возвращаться", "he": "לחזור"},
        "examples": [
            _ex(
                "Torno a casa alle sei ogni giorno.",
                "I return home at six every day.",
                "Vuelvo a casa a las seis todos los días.",
                "אני חוזר הביתה בשש כל יום.",
                "Я возвращаюсь домой в шесть каждый день.",
            ),
            _ex(
                "Siamo tornati dalle vacanze ieri sera.",
                "We got back from vacation last night.",
                "Volvimos de vacaciones anoche.",
                "חזרנו מהחופשה אתמול בערב.",
                "Мы вернулись из отпуска вчера вечером.",
            ),
            _ex(
                "Da piccolo tornavo sempre a piedi da scuola.",
                "As a child I always used to walk back from school.",
                "De pequeño siempre volvía a pie de la escuela.",
                "כשהייתי קטן תמיד הייתי חוזר ברגל מבית הספר.",
                "В детстве я всегда возвращался из школы пешком.",
            ),
            _ex(
                "Tornerò a trovarti il mese prossimo.",
                "I will come back to visit you next month.",
                "Volveré a visitarte el mes que viene.",
                "אחזור לבקר אותך בחודש הבא.",
                "Я вернусь навестить тебя в следующем месяце.",
            ),
            _ex(
                "Torna presto, ti aspettiamo per cena.",
                "Come back soon, we're waiting for you for dinner.",
                "Vuelve pronto, te esperamos para cenar.",
                "תחזור מהר, אנחנו מחכים לך לארוחת ערב.",
                "Возвращайся скорее, мы ждём тебя к ужину.",
            ),
        ],
    },
    {
        "lemma": "arrivare",
        "cls": "AR",
        "stem": "arriv",
        "aux": "essere",
        "participio": "arrivato",
        "translations": {"en": "to arrive", "es": "llegar", "ru": "прибывать", "he": "להגיע"},
        "examples": [
            _ex(
                "Arrivo sempre puntuale al lavoro.",
                "I always arrive on time for work.",
                "Siempre llego puntual al trabajo.",
                "אני תמיד מגיע בזמן לעבודה.",
                "Я всегда прихожу на работу вовремя.",
            ),
            _ex(
                "Siamo arrivati all'aeroporto con un'ora di anticipo.",
                "We arrived at the airport an hour early.",
                "Llegamos al aeropuerto con una hora de anticipación.",
                "הגענו לשדה התעופה שעה מוקדם.",
                "Мы прибыли в аэропорт на час раньше.",
            ),
            _ex(
                "Il pacco arriverà entro venerdì.",
                "The package will arrive by Friday.",
                "El paquete llegará antes del viernes.",
                "החבילה תגיע עד יום שישי.",
                "Посылка прибудет до пятницы.",
            ),
            _ex(
                "Quando ero piccolo, il postino arrivava sempre alle dieci.",
                "When I was little, the mailman always used to arrive at ten.",
                "Cuando era pequeño, el cartero siempre llegaba a las diez.",
                "כשהייתי קטן, הדוור תמיד היה מגיע בעשר.",
                "Когда я был маленьким, почтальон всегда приходил в десять.",
            ),
            _ex(
                "Stavamo arrivando quando è iniziato il temporale.",
                "We were arriving when the storm started.",
                "Estábamos llegando cuando empezó la tormenta.",
                "היינו מגיעים כשהתחילה הסופה.",
                "Мы уже подъезжали, когда начался ливень.",
            ),
        ],
    },
    {
        "lemma": "partire",
        "cls": "IR",
        "stem": "part",
        "aux": "essere",
        "participio": "partito",
        "translations": {"en": "to leave/depart", "es": "partir/irse", "ru": "уезжать", "he": "לצאת לדרך"},
        "examples": [
            _ex(
                "Parto per Roma domani mattina.",
                "I'm leaving for Rome tomorrow morning.",
                "Salgo para Roma mañana por la mañana.",
                "אני יוצא לרומא מחר בבוקר.",
                "Я уезжаю в Рим завтра утром.",
            ),
            _ex(
                "Siamo partiti troppo tardi e abbiamo perso il treno.",
                "We left too late and missed the train.",
                "Salimos demasiado tarde y perdimos el tren.",
                "יצאנו מאוחר מדי ופספסנו את הרכבת.",
                "Мы выехали слишком поздно и опоздали на поезд.",
            ),
            _ex(
                "Ogni estate partivamo per il mare a luglio.",
                "Every summer we used to leave for the seaside in July.",
                "Cada verano salíamos hacia el mar en julio.",
                "כל קיץ היינו יוצאים לים ביולי.",
                "Каждое лето мы уезжали к морю в июле.",
            ),
            _ex(
                "Partiremo appena finito di fare le valigie.",
                "We will leave as soon as we finish packing.",
                "Partiremos en cuanto terminemos de hacer las maletas.",
                "ניצא ברגע שנסיים לארוז את המזוודות.",
                "Мы отправимся, как только закончим собирать чемоданы.",
            ),
            _ex(
                "Parti pure, io ti raggiungo dopo.",
                "Go ahead and leave, I'll catch up with you later.",
                "Vete tú, yo te alcanzo después.",
                "תצא אתה, אני אצטרף אליך אחר כך.",
                "Уезжай, я догоню тебя позже.",
            ),
        ],
    },
    {
        "lemma": "sentire",
        "cls": "IR",
        "stem": "sent",
        "aux": "avere",
        "participio": "sentito",
        "translations": {"en": "to feel/hear", "es": "sentir/oír", "ru": "чувствовать/слышать", "he": "להרגיש/לשמוע"},
        "examples": [
            _ex(
                "Sento un rumore strano in cucina.",
                "I hear a strange noise in the kitchen.",
                "Oigo un ruido extraño en la cocina.",
                "אני שומע רעש מוזר במטבח.",
                "Я слышу странный шум на кухне.",
            ),
            _ex(
                "Abbiamo sentito la notizia stamattina.",
                "We heard the news this morning.",
                "Oímos la noticia esta mañana.",
                "שמענו את החדשות הבוקר.",
                "Мы услышали новость сегодня утром.",
            ),
            _ex(
                "Da ragazzo sentivo spesso la radio la sera.",
                "As a boy I often used to listen to the radio in the evening.",
                "De niño oía la radio a menudo por la noche.",
                "כשהייתי ילד הייתי שומע רדיו הרבה בערבים.",
                "В детстве я часто слушал радио по вечерам.",
            ),
            _ex(
                "Sentirò la sua opinione prima di decidere.",
                "I will hear his opinion before deciding.",
                "Escucharé su opinión antes de decidir.",
                "אשמע את דעתו לפני שאחליט.",
                "Я выслушаю его мнение, прежде чем решить.",
            ),
            _ex(
                "Senti, dobbiamo parlare un attimo.",
                "Listen, we need to talk for a moment.",
                "Oye, tenemos que hablar un momento.",
                "תקשיב, אנחנו צריכים לדבר רגע.",
                "Слушай, нам нужно поговорить минутку.",
            ),
        ],
    },
    {
        "lemma": "capire",
        "cls": "IISC",
        "stem": "cap",
        "aux": "avere",
        "participio": "capito",
        "translations": {"en": "to understand", "es": "entender", "ru": "понимать", "he": "להבין"},
        "examples": [
            _ex(
                "Capisco bene l'italiano ma lo parlo poco.",
                "I understand Italian well but I speak it little.",
                "Entiendo bien el italiano pero lo hablo poco.",
                "אני מבין איטלקית טוב אבל מדבר מעט.",
                "Я хорошо понимаю итальянский, но плохо говорю на нём.",
            ),
            _ex(
                "Non ho capito la tua domanda.",
                "I didn't understand your question.",
                "No entendí tu pregunta.",
                "לא הבנתי את השאלה שלך.",
                "Я не понял твой вопрос.",
            ),
            _ex(
                "Da bambino non capivo mai gli scherzi degli adulti.",
                "As a child I never used to understand adults' jokes.",
                "De niño nunca entendía las bromas de los adultos.",
                "כשהייתי ילד מעולם לא הבנתי את הבדיחות של המבוגרים.",
                "В детстве я никогда не понимал шуток взрослых.",
            ),
            _ex(
                "Capirai tutto quando sarai più grande.",
                "You will understand everything when you're older.",
                "Entenderás todo cuando seas mayor.",
                "תבין הכל כשתהיה יותר גדול.",
                "Ты всё поймёшь, когда станешь старше.",
            ),
            _ex(
                "Capisci bene, è importante per il tuo futuro!",
                "Understand this well, it's important for your future!",
                "¡Entiende bien esto, es importante para tu futuro!",
                "תבין את זה טוב, זה חשוב לעתיד שלך!",
                "Пойми это хорошо, это важно для твоего будущего!",
            ),
        ],
    },
    {
        "lemma": "finire",
        "cls": "IISC",
        "stem": "fin",
        "aux": "avere",
        "participio": "finito",
        "translations": {"en": "to finish", "es": "terminar", "ru": "заканчивать", "he": "לסיים"},
        "examples": [
            _ex(
                "Finisco il lavoro alle diciotto.",
                "I finish work at six pm.",
                "Termino el trabajo a las seis de la tarde.",
                "אני מסיים את העבודה בשש בערב.",
                "Я заканчиваю работу в шесть вечера.",
            ),
            _ex(
                "Abbiamo finito il progetto in tempo.",
                "We finished the project on time.",
                "Terminamos el proyecto a tiempo.",
                "סיימנו את הפרויקט בזמן.",
                "Мы закончили проект вовремя.",
            ),
            _ex(
                "Da studente finivo sempre i compiti all'ultimo momento.",
                "As a student I always used to finish my homework at the last minute.",
                "De estudiante siempre terminaba los deberes en el último momento.",
                "כשהייתי סטודנט תמיד הייתי מסיים שיעורי בית ברגע האחרון.",
                "Будучи студентом, я всегда заканчивал домашние задания в последний момент.",
            ),
            _ex(
                "Finirò questo libro entro stasera.",
                "I will finish this book by tonight.",
                "Terminaré este libro para esta noche.",
                "אסיים את הספר הזה עד הערב.",
                "Я закончу эту книгу к сегодняшнему вечеру.",
            ),
            _ex(
                "Finisci i compiti prima di uscire.",
                "Finish your homework before going out.",
                "Termina los deberes antes de salir.",
                "סיים את שיעורי הבית לפני שאתה יוצא.",
                "Закончи домашнее задание, прежде чем идти гулять.",
            ),
        ],
    },
    {
        "lemma": "cominciare",
        "cls": "ACI",
        "stem": "cominci",
        "aux": "avere",
        "participio": "cominciato",
        "translations": {"en": "to begin", "es": "empezar", "ru": "начинать", "he": "להתחיל"},
        "examples": [
            _ex(
                "Comincio a lavorare alle otto.",
                "I start working at eight.",
                "Empiezo a trabajar a las ocho.",
                "אני מתחיל לעבוד בשמונה.",
                "Я начинаю работать в восемь.",
            ),
            _ex(
                "Abbiamo cominciato il corso la settimana scorsa.",
                "We started the course last week.",
                "Empezamos el curso la semana pasada.",
                "התחלנו את הקורס בשבוע שעבר.",
                "Мы начали курс на прошлой неделе.",
            ),
            _ex(
                "Da bambino cominciavo sempre a piangere per niente.",
                "As a child I would always start crying for no reason.",
                "De niño siempre empezaba a llorar por nada.",
                "כשהייתי ילד תמיד הייתי מתחיל לבכות משום דבר.",
                "В детстве я всегда начинал плакать из-за пустяков.",
            ),
            _ex(
                "Comincerò la dieta lunedì prossimo.",
                "I will start the diet next Monday.",
                "Empezaré la dieta el próximo lunes.",
                "אתחיל בדיאטה ביום שני הבא.",
                "Я начну диету в следующий понедельник.",
            ),
            _ex(
                "Comincia subito, non c'è tempo da perdere.",
                "Start right away, there's no time to lose.",
                "Empieza ya, no hay tiempo que perder.",
                "תתחיל מיד, אין זמן לבזבז.",
                "Начинай сразу, нельзя терять время.",
            ),
        ],
    },
    {
        "lemma": "chiamare",
        "cls": "AR",
        "stem": "chiam",
        "aux": "avere",
        "participio": "chiamato",
        "translations": {"en": "to call", "es": "llamar", "ru": "звать/звонить", "he": "לקרוא/להתקשר"},
        "examples": [
            _ex(
                "Chiamo mia madre ogni domenica.",
                "I call my mother every Sunday.",
                "Llamo a mi madre todos los domingos.",
                "אני מתקשר לאמא שלי כל יום ראשון.",
                "Я звоню маме каждое воскресенье.",
            ),
            _ex(
                "Ti ho chiamato tre volte ieri sera.",
                "I called you three times last night.",
                "Te llamé tres veces anoche.",
                "התקשרתי אליך שלוש פעמים אתמול בערב.",
                "Я звонил тебе три раза вчера вечером.",
            ),
            _ex(
                "Da piccolo chiamavo sempre il nonno per raccontargli la giornata.",
                "As a child I always used to call grandpa to tell him about my day.",
                "De pequeño siempre llamaba al abuelo para contarle el día.",
                "כשהייתי קטן תמיד הייתי מתקשר לסבא לספר לו על היום שלי.",
                "В детстве я всегда звонил дедушке, чтобы рассказать о своём дне.",
            ),
            _ex(
                "Ti chiamerò appena arrivo a casa.",
                "I will call you as soon as I get home.",
                "Te llamaré en cuanto llegue a casa.",
                "אתקשר אליך ברגע שאגיע הביתה.",
                "Я позвоню тебе, как только приду домой.",
            ),
            _ex(
                "Chiamami se hai bisogno di qualcosa.",
                "Call me if you need anything.",
                "Llámame si necesitas algo.",
                "תתקשר אליי אם אתה צריך משהו.",
                "Позвони мне, если тебе что-то нужно.",
            ),
        ],
    },
    {
        "lemma": "chiedere",
        "cls": "ER",
        "stem": "chied",
        "aux": "avere",
        "participio": "chiesto",
        "translations": {"en": "to ask", "es": "preguntar/pedir", "ru": "спрашивать/просить", "he": "לשאול/לבקש"},
        "examples": [
            _ex(
                "Chiedo sempre scusa quando sbaglio.",
                "I always apologize when I make a mistake.",
                "Siempre pido perdón cuando me equivoco.",
                "אני תמיד מבקש סליחה כשאני טועה.",
                "Я всегда прошу прощения, когда ошибаюсь.",
            ),
            _ex(
                "Gli ho chiesto un favore importante.",
                "I asked him for an important favor.",
                "Le pedí un favor importante.",
                "ביקשתי ממנו טובה חשובה.",
                "Я попросил его об одном важном одолжении.",
            ),
            _ex(
                "Da bambino chiedevo sempre il perché di tutto.",
                "As a child I always used to ask why about everything.",
                "De niño siempre preguntaba el porqué de todo.",
                "כשהייתי ילד תמיד הייתי שואל למה על הכל.",
                "В детстве я всегда спрашивал, почему всё так.",
            ),
            _ex(
                "Ti chiederò aiuto se ne avrò bisogno.",
                "I will ask you for help if I need it.",
                "Te pediré ayuda si la necesito.",
                "אבקש ממך עזרה אם אצטרך.",
                "Я попрошу у тебя помощи, если понадобится.",
            ),
            _ex(
                "Chiedi pure, non c'è problema.",
                "Go ahead and ask, no problem.",
                "Pregunta nomás, no hay problema.",
                "תשאל, אין בעיה.",
                "Спрашивай, никаких проблем.",
            ),
        ],
    },
    {
        "lemma": "rispondere",
        "cls": "ER",
        "stem": "rispond",
        "aux": "avere",
        "participio": "risposto",
        "translations": {"en": "to answer", "es": "responder", "ru": "отвечать", "he": "לענות"},
        "examples": [
            _ex(
                "Rispondo sempre alle email entro un giorno.",
                "I always answer emails within a day.",
                "Siempre respondo los correos en un día.",
                "אני תמיד עונה למיילים תוך יום.",
                "Я всегда отвечаю на письма в течение дня.",
            ),
            _ex(
                "Non hai ancora risposto alla mia domanda.",
                "You still haven't answered my question.",
                "Todavía no has respondido a mi pregunta.",
                "עדיין לא ענית על השאלה שלי.",
                "Ты ещё не ответил на мой вопрос.",
            ),
            _ex(
                "Da studente rispondevo sempre volentieri alle domande del professore.",
                "As a student I always used to gladly answer the teacher's questions.",
                "De estudiante siempre respondía con gusto a las preguntas del profesor.",
                "כשהייתי סטודנט תמיד הייתי עונה בשמחה לשאלות המורה.",
                "Будучи студентом, я всегда охотно отвечал на вопросы преподавателя.",
            ),
            _ex(
                "Risponderò alla tua lettera domani.",
                "I will answer your letter tomorrow.",
                "Responderé a tu carta mañana.",
                "אענה על המכתב שלך מחר.",
                "Я отвечу на твоё письмо завтра.",
            ),
            _ex(
                "Rispondi al telefono, per favore!",
                "Answer the phone, please!",
                "¡Contesta el teléfono, por favor!",
                "תענה לטלפון, בבקשה!",
                "Ответь на телефон, пожалуйста!",
            ),
        ],
    },
    {
        "lemma": "pensare",
        "cls": "AR",
        "stem": "pens",
        "aux": "avere",
        "participio": "pensato",
        "translations": {"en": "to think", "es": "pensar", "ru": "думать", "he": "לחשוב"},
        "examples": [
            _ex(
                "Penso spesso al futuro.",
                "I often think about the future.",
                "Pienso a menudo en el futuro.",
                "אני חושב הרבה על העתיד.",
                "Я часто думаю о будущем.",
            ),
            _ex(
                "Abbiamo pensato a lungo prima di decidere.",
                "We thought for a long time before deciding.",
                "Pensamos mucho antes de decidir.",
                "חשבנו הרבה לפני שהחלטנו.",
                "Мы долго думали, прежде чем решить.",
            ),
            _ex(
                "Da giovane pensavo di diventare medico.",
                "As a young person I used to think I'd become a doctor.",
                "De joven pensaba en ser médico.",
                "כשהייתי צעיר חשבתי להיות רופא.",
                "В молодости я думал стать врачом.",
            ),
            _ex(
                "Penserò alla tua proposta stanotte.",
                "I will think about your proposal tonight.",
                "Pensaré en tu propuesta esta noche.",
                "אחשוב על ההצעה שלך הלילה.",
                "Я подумаю над твоим предложением сегодня ночью.",
            ),
            _ex(
                "Pensaci bene prima di rispondere.",
                "Think carefully before answering.",
                "Piénsalo bien antes de responder.",
                "תחשוב על זה טוב לפני שאתה עונה.",
                "Хорошо подумай, прежде чем ответить.",
            ),
        ],
    },
    {
        "lemma": "trovare",
        "cls": "AR",
        "stem": "trov",
        "aux": "avere",
        "participio": "trovato",
        "translations": {"en": "to find", "es": "encontrar", "ru": "находить", "he": "למצוא"},
        "examples": [
            _ex(
                "Trovo sempre parcheggio vicino a casa.",
                "I always find parking near home.",
                "Siempre encuentro aparcamiento cerca de casa.",
                "אני תמיד מוצא חניה ליד הבית.",
                "Я всегда нахожу парковку рядом с домом.",
            ),
            _ex(
                "Abbiamo trovato le chiavi sotto il tappeto.",
                "We found the keys under the rug.",
                "Encontramos las llaves debajo de la alfombra.",
                "מצאנו את המפתחות מתחת לשטיח.",
                "Мы нашли ключи под ковром.",
            ),
            _ex(
                "Da bambino trovavo sempre qualcosa di interessante in giardino.",
                "As a child I always used to find something interesting in the garden.",
                "De niño siempre encontraba algo interesante en el jardín.",
                "כשהייתי ילד תמיד הייתי מוצא משהו מעניין בגינה.",
                "В детстве я всегда находил что-то интересное в саду.",
            ),
            _ex(
                "Troverò una soluzione al problema.",
                "I will find a solution to the problem.",
                "Encontraré una solución al problema.",
                "אמצא פתרון לבעיה.",
                "Я найду решение проблемы.",
            ),
            _ex(
                "Trova un momento libero per chiamarmi.",
                "Find a free moment to call me.",
                "Encuentra un momento libre para llamarme.",
                "תמצא רגע פנוי להתקשר אליי.",
                "Найди свободную минутку, чтобы позвонить мне.",
            ),
        ],
    },
    {
        "lemma": "cercare",
        "cls": "ACG",
        "stem": "cerc",
        "aux": "avere",
        "participio": "cercato",
        "translations": {"en": "to look for", "es": "buscar", "ru": "искать", "he": "לחפש"},
        "examples": [
            _ex(
                "Cerco lavoro da tre mesi.",
                "I've been looking for a job for three months.",
                "Busco trabajo desde hace tres meses.",
                "אני מחפש עבודה כבר שלושה חודשים.",
                "Я ищу работу уже три месяца.",
            ),
            _ex(
                "Abbiamo cercato ovunque ma non l'abbiamo trovato.",
                "We looked everywhere but didn't find it.",
                "Buscamos por todas partes pero no lo encontramos.",
                "חיפשנו בכל מקום אבל לא מצאנו אותו.",
                "Мы искали везде, но не нашли его.",
            ),
            _ex(
                "Da giovane cercavo sempre nuove avventure.",
                "As a young person I always used to look for new adventures.",
                "De joven siempre buscaba nuevas aventuras.",
                "כשהייתי צעיר תמיד הייתי מחפש הרפתקאות חדשות.",
                "В молодости я всегда искал новые приключения.",
            ),
            _ex(
                "Cercherò un appartamento più grande.",
                "I will look for a bigger apartment.",
                "Buscaré un apartamento más grande.",
                "אחפש דירה יותר גדולה.",
                "Я поищу квартиру побольше.",
            ),
            _ex(
                "Cerca di arrivare in orario domani.",
                "Try to arrive on time tomorrow.",
                "Trata de llegar a tiempo mañana.",
                "תשתדל להגיע בזמן מחר.",
                "Постарайся приехать вовремя завтра.",
            ),
        ],
    },
    {
        "lemma": "guardare",
        "cls": "AR",
        "stem": "guard",
        "aux": "avere",
        "participio": "guardato",
        "translations": {"en": "to watch/look at", "es": "mirar", "ru": "смотреть", "he": "להסתכל"},
        "examples": [
            _ex(
                "Guardo la televisione ogni sera.",
                "I watch television every evening.",
                "Miro la televisión cada noche.",
                "אני צופה בטלוויזיה כל ערב.",
                "Я смотрю телевизор каждый вечер.",
            ),
            _ex(
                "Abbiamo guardato un bel film ieri.",
                "We watched a nice movie yesterday.",
                "Vimos una buena película ayer.",
                "צפינו בסרט יפה אתמול.",
                "Мы посмотрели хороший фильм вчера.",
            ),
            _ex(
                "Da bambino guardavo sempre i cartoni la mattina.",
                "As a child I always used to watch cartoons in the morning.",
                "De niño siempre miraba dibujos animados por la mañana.",
                "כשהייתי ילד תמיד הייתי צופה בסרטים מצוירים בבוקר.",
                "В детстве я всегда смотрел мультфильмы по утрам.",
            ),
            _ex(
                "Guarderò le foto delle vacanze stasera.",
                "I will look at the vacation photos tonight.",
                "Miraré las fotos de las vacaciones esta noche.",
                "אסתכל בתמונות מהחופשה הערב.",
                "Я посмотрю фотографии с отпуска сегодня вечером.",
            ),
            _ex(
                "Guarda bene prima di attraversare la strada.",
                "Look carefully before crossing the street.",
                "Mira bien antes de cruzar la calle.",
                "תסתכל טוב לפני שאתה חוצה את הכביש.",
                "Хорошо посмотри, прежде чем переходить улицу.",
            ),
        ],
    },
    {
        "lemma": "ascoltare",
        "cls": "AR",
        "stem": "ascolt",
        "aux": "avere",
        "participio": "ascoltato",
        "translations": {"en": "to listen to", "es": "escuchar", "ru": "слушать", "he": "להקשיב"},
        "examples": [
            _ex(
                "Ascolto la musica mentre lavoro.",
                "I listen to music while I work.",
                "Escucho música mientras trabajo.",
                "אני מקשיב למוזיקה בזמן שאני עובד.",
                "Я слушаю музыку, пока работаю.",
            ),
            _ex(
                "Abbiamo ascoltato tutto il concerto in piedi.",
                "We listened to the whole concert standing up.",
                "Escuchamos todo el concierto de pie.",
                "הקשבנו לכל הקונצרט בעמידה.",
                "Мы прослушали весь концерт стоя.",
            ),
            _ex(
                "Da ragazzo ascoltavo la radio ogni pomeriggio.",
                "As a boy I used to listen to the radio every afternoon.",
                "De joven escuchaba la radio todas las tardes.",
                "כשהייתי נער הייתי מקשיב לרדיו כל אחר צהריים.",
                "В юности я слушал радио каждый день после обеда.",
            ),
            _ex(
                "Ascolterò il tuo consiglio questa volta.",
                "I will listen to your advice this time.",
                "Escucharé tu consejo esta vez.",
                "אקשיב לעצה שלך הפעם.",
                "На этот раз я послушаю твой совет.",
            ),
            _ex(
                "Ascolta attentamente quello che sto per dirti.",
                "Listen carefully to what I'm about to tell you.",
                "Escucha atentamente lo que te voy a decir.",
                "תקשיב היטב למה שאני עומד להגיד לך.",
                "Слушай внимательно, что я тебе сейчас скажу.",
            ),
        ],
    },
    {
        "lemma": "leggere",
        "cls": "ER",
        "stem": "legg",
        "aux": "avere",
        "participio": "letto",
        "translations": {"en": "to read", "es": "leer", "ru": "читать", "he": "לקרוא"},
        "examples": [
            _ex(
                "Leggo il giornale ogni mattina.",
                "I read the newspaper every morning.",
                "Leo el periódico cada mañana.",
                "אני קורא עיתון כל בוקר.",
                "Я читаю газету каждое утро.",
            ),
            _ex(
                "Abbiamo letto tutto il libro in un weekend.",
                "We read the whole book in a weekend.",
                "Leímos todo el libro en un fin de semana.",
                "קראנו את כל הספר בסוף שבוע אחד.",
                "Мы прочитали всю книгу за выходные.",
            ),
            _ex(
                "Da bambino leggevo fumetti tutto il giorno.",
                "As a child I used to read comics all day.",
                "De niño leía cómics todo el día.",
                "כשהייתי ילד הייתי קורא קומיקס כל היום.",
                "В детстве я целыми днями читал комиксы.",
            ),
            _ex(
                "Leggerò il tuo rapporto domani mattina.",
                "I will read your report tomorrow morning.",
                "Leeré tu informe mañana por la mañana.",
                "אקרא את הדוח שלך מחר בבוקר.",
                "Я прочитаю твой отчёт завтра утром.",
            ),
            _ex(
                "Leggi con attenzione le istruzioni.",
                "Read the instructions carefully.",
                "Lee atentamente las instrucciones.",
                "תקרא בעיון את ההוראות.",
                "Внимательно прочитай инструкции.",
            ),
        ],
    },
    {
        "lemma": "scrivere",
        "cls": "ER",
        "stem": "scriv",
        "aux": "avere",
        "participio": "scritto",
        "translations": {"en": "to write", "es": "escribir", "ru": "писать", "he": "לכתוב"},
        "examples": [
            _ex(
                "Scrivo un diario ogni sera.",
                "I write a diary every evening.",
                "Escribo un diario cada noche.",
                "אני כותב יומן כל ערב.",
                "Я пишу дневник каждый вечер.",
            ),
            _ex(
                "Ho scritto una lettera lunga ai miei genitori.",
                "I wrote a long letter to my parents.",
                "Escribí una carta larga a mis padres.",
                "כתבתי מכתב ארוך להורים שלי.",
                "Я написал длинное письмо родителям.",
            ),
            _ex(
                "Da giovane scrivevo poesie nel tempo libero.",
                "As a young person I used to write poems in my free time.",
                "De joven escribía poemas en mi tiempo libre.",
                "כשהייתי צעיר הייתי כותב שירים בזמן הפנוי.",
                "В молодости я писал стихи в свободное время.",
            ),
            _ex(
                "Ti scriverò appena avrò notizie.",
                "I will write to you as soon as I have news.",
                "Te escribiré en cuanto tenga noticias.",
                "אכתוב לך ברגע שיהיו חדשות.",
                "Я напишу тебе, как только будут новости.",
            ),
            _ex(
                "Scrivi il tuo nome qui in fondo.",
                "Write your name here at the bottom.",
                "Escribe tu nombre aquí abajo.",
                "תכתוב את השם שלך כאן למטה.",
                "Напиши своё имя здесь внизу.",
            ),
        ],
    },
    {
        "lemma": "studiare",
        "cls": "AR",
        "stem": "studi",
        "aux": "avere",
        "participio": "studiato",
        "translations": {"en": "to study", "es": "estudiar", "ru": "учиться/изучать", "he": "ללמוד"},
        "examples": [
            _ex(
                "Studio l'inglese da due anni.",
                "I've been studying English for two years.",
                "Estudio inglés desde hace dos años.",
                "אני לומד אנגלית כבר שנתיים.",
                "Я изучаю английский уже два года.",
            ),
            _ex(
                "Abbiamo studiato tutta la notte per l'esame.",
                "We studied all night for the exam.",
                "Estudiamos toda la noche para el examen.",
                "למדנו כל הלילה למבחן.",
                "Мы всю ночь готовились к экзамену.",
            ),
            _ex(
                "Da ragazzo studiavo poco e giocavo molto.",
                "As a boy I used to study little and play a lot.",
                "De joven estudiaba poco y jugaba mucho.",
                "כשהייתי נער הייתי לומד מעט ומשחק הרבה.",
                "В юности я мало учился и много играл.",
            ),
            _ex(
                "Studierò medicina all'università.",
                "I will study medicine at university.",
                "Estudiaré medicina en la universidad.",
                "אלמד רפואה באוניברסיטה.",
                "Я буду изучать медицину в университете.",
            ),
            _ex(
                "Studia con attenzione prima dell'esame.",
                "Study carefully before the exam.",
                "Estudia con atención antes del examen.",
                "תלמד בתשומת לב לפני המבחן.",
                "Учись внимательно перед экзаменом.",
            ),
        ],
    },
    {
        "lemma": "imparare",
        "cls": "AR",
        "stem": "impar",
        "aux": "avere",
        "participio": "imparato",
        "translations": {"en": "to learn", "es": "aprender", "ru": "учить(ся)/изучать", "he": "ללמוד (משהו)"},
        "examples": [
            _ex(
                "Imparo una nuova lingua ogni anno.",
                "I learn a new language every year.",
                "Aprendo un idioma nuevo cada año.",
                "אני לומד שפה חדשה כל שנה.",
                "Я изучаю новый язык каждый год.",
            ),
            _ex(
                "Abbiamo imparato molto durante il viaggio.",
                "We learned a lot during the trip.",
                "Aprendimos mucho durante el viaje.",
                "למדנו הרבה במהלך הטיול.",
                "Мы многому научились во время поездки.",
            ),
            _ex(
                "Da bambino imparavo velocemente le canzoni.",
                "As a child I used to learn songs quickly.",
                "De niño aprendía las canciones rápidamente.",
                "כשהייתי ילד הייתי לומד שירים מהר.",
                "В детстве я быстро запоминал песни.",
            ),
            _ex(
                "Imparerò a nuotare quest'estate.",
                "I will learn to swim this summer.",
                "Aprenderé a nadar este verano.",
                "אלמד לשחות בקיץ הזה.",
                "Этим летом я научусь плавать.",
            ),
            _ex(
                "Impara questa lezione a memoria.",
                "Learn this lesson by heart.",
                "Aprende esta lección de memoria.",
                "תלמד את השיעור הזה בעל פה.",
                "Выучи этот урок наизусть.",
            ),
        ],
    },
    {
        "lemma": "insegnare",
        "cls": "AR",
        "stem": "insegn",
        "aux": "avere",
        "participio": "insegnato",
        "translations": {"en": "to teach", "es": "enseñar", "ru": "преподавать", "he": "ללמד"},
        "examples": [
            _ex(
                "Insegno matematica al liceo.",
                "I teach math at high school.",
                "Enseño matemáticas en el instituto.",
                "אני מלמד מתמטיקה בתיכון.",
                "Я преподаю математику в старших классах.",
            ),
            _ex(
                "Mio padre mi ha insegnato a guidare.",
                "My father taught me how to drive.",
                "Mi padre me enseñó a conducir.",
                "אבא שלי לימד אותי לנהוג.",
                "Мой отец научил меня водить машину.",
            ),
            _ex(
                "Da giovane insegnavo il pianoforte ai bambini.",
                "As a young person I used to teach piano to children.",
                "De joven enseñaba piano a los niños.",
                "כשהייתי צעיר לימדתי פסנתר לילדים.",
                "В молодости я преподавал фортепиано детям.",
            ),
            _ex(
                "Ti insegnerò a cucinare la pasta.",
                "I will teach you how to cook pasta.",
                "Te enseñaré a cocinar pasta.",
                "אלמד אותך לבשל פסטה.",
                "Я научу тебя готовить пасту.",
            ),
            _ex(
                "Insegnami come si fa, per favore.",
                "Teach me how it's done, please.",
                "Enséñame cómo se hace, por favor.",
                "תלמד אותי איך עושים את זה, בבקשה.",
                "Научи меня, как это делается, пожалуйста.",
            ),
        ],
    },
    {
        "lemma": "giocare",
        "cls": "ACG",
        "stem": "gioc",
        "aux": "avere",
        "participio": "giocato",
        "translations": {"en": "to play", "es": "jugar", "ru": "играть", "he": "לשחק"},
        "examples": [
            _ex(
                "Gioco a calcio ogni domenica.",
                "I play soccer every Sunday.",
                "Juego al fútbol todos los domingos.",
                "אני משחק כדורגל כל יום ראשון.",
                "Я играю в футбол каждое воскресенье.",
            ),
            _ex(
                "Abbiamo giocato a carte fino a tardi.",
                "We played cards until late.",
                "Jugamos a las cartas hasta tarde.",
                "שיחקנו קלפים עד מאוחר.",
                "Мы играли в карты допоздна.",
            ),
            _ex(
                "Da bambino giocavo sempre in cortile con gli amici.",
                "As a child I always used to play in the yard with friends.",
                "De niño siempre jugaba en el patio con los amigos.",
                "כשהייתי ילד תמיד הייתי משחק בחצר עם חברים.",
                "В детстве я всегда играл во дворе с друзьями.",
            ),
            _ex(
                "Giocheremo a tennis sabato prossimo.",
                "We will play tennis next Saturday.",
                "Jugaremos al tenis el próximo sábado.",
                "נשחק טניס בשבת הבאה.",
                "В следующую субботу мы поиграем в теннис.",
            ),
            _ex(
                "Gioca con tuo fratello un po'.",
                "Play with your brother for a bit.",
                "Juega un rato con tu hermano.",
                "תשחק קצת עם אחיך.",
                "Поиграй немного с братом.",
            ),
        ],
    },
    {
        "lemma": "correre",
        "cls": "ER",
        "stem": "corr",
        "aux": "avere",
        "participio": "corso",
        "translations": {"en": "to run", "es": "correr", "ru": "бегать", "he": "לרוץ"},
        "examples": [
            _ex(
                "Corro ogni mattina nel parco.",
                "I run every morning in the park.",
                "Corro cada mañana en el parque.",
                "אני רץ כל בוקר בפארק.",
                "Я бегаю каждое утро в парке.",
            ),
            _ex(
                "Ho corso per venti minuti oggi.",
                "I ran for twenty minutes today.",
                "Corrí veinte minutos hoy.",
                "רצתי עשרים דקות היום.",
                "Сегодня я бегал двадцать минут.",
            ),
            _ex(
                "Da ragazzo correvo velocissimo.",
                "As a boy I used to run very fast.",
                "De joven corría muy rápido.",
                "כשהייתי נער רצתי מהר מאוד.",
                "В юности я бегал очень быстро.",
            ),
            _ex(
                "Correrò la maratona l'anno prossimo.",
                "I will run the marathon next year.",
                "Correré la maratón el año que viene.",
                "ארוץ במרתון בשנה הבאה.",
                "В следующем году я пробегу марафон.",
            ),
            _ex(
                "Corri, siamo in ritardo!",
                "Run, we're late!",
                "¡Corre, vamos tarde!",
                "תרוץ, אנחנו מאחרים!",
                "Беги, мы опаздываем!",
            ),
        ],
    },
    {
        "lemma": "camminare",
        "cls": "AR",
        "stem": "cammin",
        "aux": "avere",
        "participio": "camminato",
        "translations": {"en": "to walk", "es": "caminar", "ru": "ходить пешком", "he": "ללכת ברגל"},
        "examples": [
            _ex(
                "Cammino un'ora ogni giorno per stare in forma.",
                "I walk an hour every day to stay fit.",
                "Camino una hora cada día para mantenerme en forma.",
                "אני הולך ברגל שעה כל יום כדי להישאר בכושר.",
                "Я хожу пешком час каждый день, чтобы быть в форме.",
            ),
            _ex(
                "Abbiamo camminato per tutta la città ieri.",
                "We walked all over the city yesterday.",
                "Caminamos por toda la ciudad ayer.",
                "הלכנו ברגל בכל העיר אתמול.",
                "Вчера мы прошли пешком по всему городу.",
            ),
            _ex(
                "Da bambino camminavo sempre scalzo in giardino.",
                "As a child I always used to walk barefoot in the garden.",
                "De niño caminaba siempre descalzo en el jardín.",
                "כשהייתי ילד תמיד הייתי הולך יחף בגינה.",
                "В детстве я всегда ходил босиком по саду.",
            ),
            _ex(
                "Cammineremo fino al centro se non piove.",
                "We will walk to downtown if it doesn't rain.",
                "Caminaremos hasta el centro si no llueve.",
                "נלך ברגל למרכז אם לא ירד גשם.",
                "Мы дойдём до центра пешком, если не будет дождя.",
            ),
            _ex(
                "Cammina piano, il pavimento è bagnato.",
                "Walk slowly, the floor is wet.",
                "Camina despacio, el suelo está mojado.",
                "תלך לאט, הרצפה רטובה.",
                "Иди медленно, пол мокрый.",
            ),
        ],
    },
    {
        "lemma": "aprire",
        "cls": "IR",
        "stem": "apr",
        "aux": "avere",
        "participio": "aperto",
        "translations": {"en": "to open", "es": "abrir", "ru": "открывать", "he": "לפתוח"},
        "examples": [
            _ex(
                "Apro la finestra ogni mattina per arieggiare.",
                "I open the window every morning to air out the room.",
                "Abro la ventana cada mañana para airear.",
                "אני פותח את החלון כל בוקר כדי לאוורר.",
                "Я каждое утро открываю окно, чтобы проветрить.",
            ),
            _ex(
                "Abbiamo aperto un nuovo negozio in centro.",
                "We opened a new store downtown.",
                "Abrimos una nueva tienda en el centro.",
                "פתחנו חנות חדשה במרכז.",
                "Мы открыли новый магазин в центре.",
            ),
            _ex(
                "Da bambino aprivo sempre i regali prima di Natale.",
                "As a child I always used to open presents before Christmas.",
                "De niño siempre abría los regalos antes de Navidad.",
                "כשהייתי ילד תמיד הייתי פותח מתנות לפני חג המולד.",
                "В детстве я всегда открывал подарки до Рождества.",
            ),
            _ex(
                "Apriremo il negozio alle nove domani.",
                "We will open the shop at nine tomorrow.",
                "Abriremos la tienda a las nueve mañana.",
                "נפתח את החנות בתשע מחר.",
                "Завтра мы откроем магазин в девять.",
            ),
            _ex(
                "Apri la porta, per favore.",
                "Open the door, please.",
                "Abre la puerta, por favor.",
                "תפתח את הדלת, בבקשה.",
                "Открой дверь, пожалуйста.",
            ),
        ],
    },
    {
        "lemma": "chiudere",
        "cls": "ER",
        "stem": "chiud",
        "aux": "avere",
        "participio": "chiuso",
        "translations": {"en": "to close", "es": "cerrar", "ru": "закрывать", "he": "לסגור"},
        "examples": [
            _ex(
                "Chiudo sempre la porta a chiave la sera.",
                "I always lock the door at night.",
                "Siempre cierro la puerta con llave por la noche.",
                "אני תמיד נועל את הדלת בלילה.",
                "Я всегда закрываю дверь на ключ вечером.",
            ),
            _ex(
                "Abbiamo chiuso il negozio prima del solito.",
                "We closed the shop earlier than usual.",
                "Cerramos la tienda antes de lo habitual.",
                "סגרנו את החנות מוקדם יותר מהרגיל.",
                "Мы закрыли магазин раньше обычного.",
            ),
            _ex(
                "Da bambino chiudevo sempre gli occhi durante i film di paura.",
                "As a child I always used to close my eyes during scary movies.",
                "De niño siempre cerraba los ojos durante las películas de miedo.",
                "כשהייתי ילד תמיד הייתי עוצם עיניים בסרטי אימה.",
                "В детстве я всегда закрывал глаза во время страшных фильмов.",
            ),
            _ex(
                "Chiuderemo l'ufficio per le vacanze.",
                "We will close the office for the holidays.",
                "Cerraremos la oficina por las vacaciones.",
                "נסגור את המשרד לחופשה.",
                "Мы закроем офис на время каникул.",
            ),
            _ex(
                "Chiudi bene la valigia prima di partire.",
                "Close the suitcase properly before leaving.",
                "Cierra bien la maleta antes de salir.",
                "תסגור טוב את המזוודה לפני שאתה יוצא.",
                "Хорошо закрой чемодан перед отъездом.",
            ),
        ],
    },
    {
        "lemma": "comprare",
        "cls": "AR",
        "stem": "compr",
        "aux": "avere",
        "participio": "comprato",
        "translations": {"en": "to buy", "es": "comprar", "ru": "покупать", "he": "לקנות"},
        "examples": [
            _ex(
                "Compro il pane fresco ogni mattina.",
                "I buy fresh bread every morning.",
                "Compro pan fresco cada mañana.",
                "אני קונה לחם טרי כל בוקר.",
                "Я покупаю свежий хлеб каждое утро.",
            ),
            _ex(
                "Abbiamo comprato una macchina nuova.",
                "We bought a new car.",
                "Compramos un coche nuevo.",
                "קנינו מכונית חדשה.",
                "Мы купили новую машину.",
            ),
            _ex(
                "Da bambino compravo caramelle con la paghetta.",
                "As a child I used to buy candy with my allowance.",
                "De niño compraba caramelos con la paga.",
                "כשהייתי ילד הייתי קונה סוכריות מדמי הכיס.",
                "В детстве я покупал конфеты на карманные деньги.",
            ),
            _ex(
                "Comprerò un regalo per il suo compleanno.",
                "I will buy a gift for their birthday.",
                "Compraré un regalo para su cumpleaños.",
                "אקנה מתנה ליום ההולדת שלו.",
                "Я куплю подарок на день рождения.",
            ),
            _ex(
                "Compra un po' di frutta al mercato.",
                "Buy some fruit at the market.",
                "Compra un poco de fruta en el mercado.",
                "תקנה קצת פירות בשוק.",
                "Купи немного фруктов на рынке.",
            ),
        ],
    },
    {
        "lemma": "vendere",
        "cls": "ER",
        "stem": "vend",
        "aux": "avere",
        "participio": "venduto",
        "translations": {"en": "to sell", "es": "vender", "ru": "продавать", "he": "למכור"},
        "examples": [
            _ex(
                "Vendo prodotti artigianali online.",
                "I sell handmade products online.",
                "Vendo productos artesanales en línea.",
                "אני מוכר מוצרים בעבודת יד באינטרנט.",
                "Я продаю изделия ручной работы онлайн.",
            ),
            _ex(
                "Abbiamo venduto la casa vecchia l'anno scorso.",
                "We sold the old house last year.",
                "Vendimos la casa vieja el año pasado.",
                "מכרנו את הבית הישן בשנה שעברה.",
                "Мы продали старый дом в прошлом году.",
            ),
            _ex(
                "Da giovane vendevo giornali all'angolo della strada.",
                "As a young person I used to sell newspapers on the street corner.",
                "De joven vendía periódicos en la esquina.",
                "כשהייתי צעיר מכרתי עיתונים בפינת הרחוב.",
                "В молодости я продавал газеты на углу улицы.",
            ),
            _ex(
                "Venderò la mia bicicletta il mese prossimo.",
                "I will sell my bike next month.",
                "Venderé mi bicicleta el mes que viene.",
                "אמכור את האופניים שלי בחודש הבא.",
                "В следующем месяце я продам свой велосипед.",
            ),
            _ex(
                "Vendi pure quello che non usi più.",
                "Go ahead and sell what you no longer use.",
                "Vende lo que ya no uses.",
                "תמכור את מה שאתה כבר לא משתמש בו.",
                "Продай то, чем ты больше не пользуешься.",
            ),
        ],
    },
    {
        "lemma": "pagare",
        "cls": "ACG",
        "stem": "pag",
        "aux": "avere",
        "participio": "pagato",
        "translations": {"en": "to pay", "es": "pagar", "ru": "платить", "he": "לשלם"},
        "examples": [
            _ex(
                "Pago le bollette online ogni mese.",
                "I pay the bills online every month.",
                "Pago las facturas en línea cada mes.",
                "אני משלם את החשבונות באינטרנט כל חודש.",
                "Я оплачиваю счета онлайн каждый месяц.",
            ),
            _ex(
                "Abbiamo pagato il conto al ristorante.",
                "We paid the bill at the restaurant.",
                "Pagamos la cuenta en el restaurante.",
                "שילמנו את החשבון במסעדה.",
                "Мы оплатили счёт в ресторане.",
            ),
            _ex(
                "Da studente pagavo l'affitto con fatica.",
                "As a student I used to struggle to pay the rent.",
                "De estudiante pagaba el alquiler con esfuerzo.",
                "כשהייתי סטודנט הייתי משלם שכר דירה בקושי.",
                "Будучи студентом, я с трудом платил за квартиру.",
            ),
            _ex(
                "Pagherò il resto la prossima settimana.",
                "I will pay the rest next week.",
                "Pagaré el resto la próxima semana.",
                "אשלם את השאר בשבוע הבא.",
                "Я заплачу остаток на следующей неделе.",
            ),
            _ex(
                "Paga alla cassa, per favore.",
                "Pay at the register, please.",
                "Paga en la caja, por favor.",
                "תשלם בקופה, בבקשה.",
                "Оплатите на кассе, пожалуйста.",
            ),
        ],
    },
    {
        "lemma": "portare",
        "cls": "AR",
        "stem": "port",
        "aux": "avere",
        "participio": "portato",
        "translations": {"en": "to carry/bring", "es": "llevar/traer", "ru": "нести/приносить", "he": "לשאת/להביא"},
        "examples": [
            _ex(
                "Porto sempre l'ombrello quando piove.",
                "I always carry an umbrella when it rains.",
                "Siempre llevo el paraguas cuando llueve.",
                "אני תמיד לוקח מטריה כשיורד גשם.",
                "Я всегда беру зонт, когда идёт дождь.",
            ),
            _ex(
                "Ho portato i documenti in ufficio stamattina.",
                "I brought the documents to the office this morning.",
                "Traje los documentos a la oficina esta mañana.",
                "הבאתי את המסמכים למשרד הבוקר.",
                "Сегодня утром я принёс документы в офис.",
            ),
            _ex(
                "Da bambino portavo sempre lo zaino pesante a scuola.",
                "As a child I always used to carry a heavy backpack to school.",
                "De niño siempre llevaba la mochila pesada a la escuela.",
                "כשהייתי ילד תמיד הייתי נושא תיק כבד לבית הספר.",
                "В детстве я всегда носил тяжёлый рюкзак в школу.",
            ),
            _ex(
                "Ti porterò un regalo dal viaggio.",
                "I will bring you a gift from the trip.",
                "Te traeré un regalo del viaje.",
                "אביא לך מתנה מהטיול.",
                "Я привезу тебе подарок из поездки.",
            ),
            _ex(
                "Porta questi libri in biblioteca, per favore.",
                "Bring these books to the library, please.",
                "Lleva estos libros a la biblioteca, por favor.",
                "תביא את הספרים האלה לספרייה, בבקשה.",
                "Отнеси эти книги в библиотеку, пожалуйста.",
            ),
        ],
    },
    {
        "lemma": "lasciare",
        "cls": "ACI",
        "stem": "lasci",
        "aux": "avere",
        "participio": "lasciato",
        "translations": {"en": "to leave/let", "es": "dejar", "ru": "оставлять", "he": "להשאיר/לעזוב"},
        "examples": [
            _ex(
                "Lascio sempre le chiavi sul tavolo.",
                "I always leave the keys on the table.",
                "Siempre dejo las llaves en la mesa.",
                "אני תמיד משאיר את המפתחות על השולחן.",
                "Я всегда оставляю ключи на столе.",
            ),
            _ex(
                "Abbiamo lasciato la città dopo dieci anni.",
                "We left the city after ten years.",
                "Dejamos la ciudad después de diez años.",
                "עזבנו את העיר אחרי עשר שנים.",
                "Мы покинули город спустя десять лет.",
            ),
            _ex(
                "Da giovane lasciavo sempre tutto all'ultimo momento.",
                "As a young person I always used to leave everything to the last minute.",
                "De joven siempre dejaba todo para el último momento.",
                "כשהייתי צעיר תמיד הייתי משאיר הכל לרגע האחרון.",
                "В молодости я всегда всё оставлял на последний момент.",
            ),
            _ex(
                "Lascerò questo lavoro alla fine dell'anno.",
                "I will leave this job at the end of the year.",
                "Dejaré este trabajo a fin de año.",
                "אעזוב את העבודה הזו בסוף השנה.",
                "Я оставлю эту работу в конце года.",
            ),
            _ex(
                "Lascia stare, non è importante.",
                "Let it go, it's not important.",
                "Déjalo, no es importante.",
                "תעזוב את זה, זה לא חשוב.",
                "Оставь это, это неважно.",
            ),
        ],
    },
    {
        "lemma": "restare",
        "cls": "AR",
        "stem": "rest",
        "aux": "essere",
        "participio": "restato",
        "translations": {"en": "to stay", "es": "quedarse", "ru": "оставаться", "he": "להישאר"},
        "examples": [
            _ex(
                "Resto a casa quando piove.",
                "I stay home when it rains.",
                "Me quedo en casa cuando llueve.",
                "אני נשאר בבית כשיורד גשם.",
                "Я остаюсь дома, когда идёт дождь.",
            ),
            _ex(
                "Siamo restati svegli fino a tardi.",
                "We stayed awake until late.",
                "Nos quedamos despiertos hasta tarde.",
                "נשארנו ערים עד מאוחר.",
                "Мы не спали допоздна.",
            ),
            _ex(
                "Da bambino restavo sempre vicino a mia madre.",
                "As a child I always used to stay close to my mother.",
                "De niño siempre me quedaba cerca de mi madre.",
                "כשהייתי ילד תמיד הייתי נשאר קרוב לאמא שלי.",
                "В детстве я всегда оставался рядом с мамой.",
            ),
            _ex(
                "Resterò in ufficio fino a tardi stasera.",
                "I will stay at the office late tonight.",
                "Me quedaré en la oficina hasta tarde esta noche.",
                "אשאר במשרד עד מאוחר הערב.",
                "Сегодня вечером я останусь в офисе допоздна.",
            ),
            _ex(
                "Resta ancora un po', non andare via.",
                "Stay a bit longer, don't leave.",
                "Quédate un poco más, no te vayas.",
                "תישאר עוד קצת, אל תלך.",
                "Останься ещё немного, не уходи.",
            ),
        ],
    },
    {
        # No natural imperativo example: "Sembra!" as a bare command doesn't
        # work in real Italian (sembrare is a stative/impersonal-leaning verb,
        # same class of gap fix_fr_pouvoir_imperative.py addresses for French's
        # defective pouvoir) -- substituted a progressive stare+gerundio example
        # in its place instead of forcing a contrived command sentence.
        "lemma": "sembrare",
        "cls": "AR",
        "stem": "sembr",
        "aux": "essere",
        "participio": "sembrato",
        "translations": {"en": "to seem", "es": "parecer", "ru": "казаться", "he": "להיראות"},
        "examples": [
            _ex(
                "Sembri stanco oggi, va tutto bene?",
                "You seem tired today, is everything okay?",
                "Pareces cansado hoy, ¿va todo bien?",
                "אתה נראה עייף היום, הכל בסדר?",
                "Ты сегодня выглядишь уставшим, всё в порядке?",
            ),
            _ex(
                "Il film ci è sembrato troppo lungo.",
                "The movie seemed too long to us.",
                "La película nos pareció demasiado larga.",
                "הסרט נראה לנו ארוך מדי.",
                "Фильм показался нам слишком длинным.",
            ),
            _ex(
                "Da lontano la casa sembrava più piccola.",
                "From a distance the house used to seem smaller.",
                "Desde lejos la casa parecía más pequeña.",
                "מרחוק הבית נראה יותר קטן.",
                "Издалека дом казался меньше.",
            ),
            _ex(
                "Domani sembrerà tutto più semplice, vedrai.",
                "Tomorrow everything will seem simpler, you'll see.",
                "Mañana todo parecerá más sencillo, ya verás.",
                "מחר הכל ייראה פשוט יותר, תראה.",
                "Завтра всё будет казаться проще, вот увидишь.",
            ),
            _ex(
                "Mi stava sembrando una buona idea, poi ho cambiato idea.",
                "It was starting to seem like a good idea to me, then I changed my mind.",
                "Me estaba pareciendo una buena idea, luego cambié de opinión.",
                "זה התחיל להיראות לי כמו רעיון טוב, אחר כך שיניתי את דעתי.",
                "Мне это начинало казаться хорошей идеей, потом я передумал.",
            ),
        ],
    },
    {
        # No natural bare imperativo example either (see sembrare note above) --
        # substituted a "stare + gerundio" progressive instead.
        "lemma": "diventare",
        "cls": "AR",
        "stem": "divent",
        "aux": "essere",
        "participio": "diventato",
        "translations": {"en": "to become", "es": "convertirse en/llegar a ser", "ru": "становиться", "he": "להפוך ל"},
        "examples": [
            _ex(
                "Divento nervoso prima degli esami.",
                "I become nervous before exams.",
                "Me pongo nervioso antes de los exámenes.",
                "אני נעשה עצבני לפני מבחנים.",
                "Я становлюсь нервным перед экзаменами.",
            ),
            _ex(
                "È diventato famoso dopo quel film.",
                "He became famous after that movie.",
                "Se hizo famoso después de esa película.",
                "הוא הפך למפורסם אחרי הסרט ההוא.",
                "Он стал знаменитым после того фильма.",
            ),
            _ex(
                "Da giovane diventavo rosso ogni volta che parlavo in pubblico.",
                "As a young person I used to blush every time I spoke in public.",
                "De joven me ponía rojo cada vez que hablaba en público.",
                "כשהייתי צעיר הייתי מסמיק בכל פעם שדיברתי בציבור.",
                "В молодости я краснел каждый раз, когда выступал на публике.",
            ),
            _ex(
                "Diventerai un ottimo medico un giorno.",
                "You will become an excellent doctor one day.",
                "Llegarás a ser un excelente médico algún día.",
                "תהפוך לרופא מצוין יום אחד.",
                "Однажды ты станешь отличным врачом.",
            ),
            _ex(
                "Sta diventando sempre più difficile trovare lavoro.",
                "It's becoming increasingly difficult to find a job.",
                "Se está volviendo cada vez más difícil encontrar trabajo.",
                "זה נהיה קשה יותר ויותר למצוא עבודה.",
                "Становится всё труднее найти работу.",
            ),
        ],
    },
    {
        "lemma": "aiutare",
        "cls": "AR",
        "stem": "aiut",
        "aux": "avere",
        "participio": "aiutato",
        "translations": {"en": "to help", "es": "ayudar", "ru": "помогать", "he": "לעזור"},
        "examples": [
            _ex(
                "Aiuto sempre i miei vicini quando posso.",
                "I always help my neighbors when I can.",
                "Siempre ayudo a mis vecinos cuando puedo.",
                "אני תמיד עוזר לשכנים שלי כשאני יכול.",
                "Я всегда помогаю соседям, когда могу.",
            ),
            _ex(
                "Ci hanno aiutato a traslocare il mese scorso.",
                "They helped us move last month.",
                "Nos ayudaron a mudarnos el mes pasado.",
                "הם עזרו לנו לעבור דירה בחודש שעבר.",
                "В прошлом месяце они помогли нам переехать.",
            ),
            _ex(
                "Da bambino aiutavo mia nonna in cucina.",
                "As a child I used to help my grandmother in the kitchen.",
                "De niño ayudaba a mi abuela en la cocina.",
                "כשהייתי ילד עזרתי לסבתא שלי במטבח.",
                "В детстве я помогал бабушке на кухне.",
            ),
            _ex(
                "Ti aiuterò a finire il progetto stasera.",
                "I will help you finish the project tonight.",
                "Te ayudaré a terminar el proyecto esta noche.",
                "אעזור לך לסיים את הפרויקט הערב.",
                "Я помогу тебе закончить проект сегодня вечером.",
            ),
            _ex(
                "Aiutami a portare queste scatole, per favore.",
                "Help me carry these boxes, please.",
                "Ayúdame a llevar estas cajas, por favor.",
                "תעזור לי לשאת את הקופסאות האלה, בבקשה.",
                "Помоги мне отнести эти коробки, пожалуйста.",
            ),
        ],
    },
    {
        "lemma": "ricordare",
        "cls": "AR",
        "stem": "ricord",
        "aux": "avere",
        "participio": "ricordato",
        "translations": {"en": "to remember", "es": "recordar", "ru": "помнить/вспоминать", "he": "לזכור"},
        "examples": [
            _ex(
                "Ricordo ancora il mio primo giorno di scuola.",
                "I still remember my first day of school.",
                "Todavía recuerdo mi primer día de escuela.",
                "אני עדיין זוכר את היום הראשון שלי בבית הספר.",
                "Я до сих пор помню свой первый день в школе.",
            ),
            _ex(
                "Ci siamo ricordati del suo compleanno all'ultimo momento.",
                "We remembered his birthday at the last minute.",
                "Nos acordamos de su cumpleaños en el último momento.",
                "נזכרנו ביום ההולדת שלו ברגע האחרון.",
                "Мы вспомнили о его дне рождения в последний момент.",
            ),
            _ex(
                "Da bambino non ricordavo mai dove mettevo le chiavi.",
                "As a child I never used to remember where I put my keys.",
                "De niño nunca recordaba dónde ponía las llaves.",
                "כשהייתי ילד מעולם לא זכרתי איפה שמתי את המפתחות.",
                "В детстве я никогда не помнил, куда кладу ключи.",
            ),
            _ex(
                "Mi ricorderò sempre di questo momento.",
                "I will always remember this moment.",
                "Siempre recordaré este momento.",
                "אני תמיד אזכור את הרגע הזה.",
                "Я всегда буду помнить этот момент.",
            ),
            _ex(
                "Ricorda di chiudere la porta a chiave.",
                "Remember to lock the door.",
                "Recuerda cerrar la puerta con llave.",
                "תזכור לנעול את הדלת.",
                "Не забудь закрыть дверь на ключ.",
            ),
        ],
    },
    {
        "lemma": "dimenticare",
        "cls": "ACG",
        "stem": "dimentic",
        "aux": "avere",
        "participio": "dimenticato",
        "translations": {"en": "to forget", "es": "olvidar", "ru": "забывать", "he": "לשכוח"},
        "examples": [
            _ex(
                "Dimentico spesso dove metto le chiavi.",
                "I often forget where I put my keys.",
                "A menudo olvido dónde pongo las llaves.",
                "אני שוכח לעתים קרובות איפה אני שם את המפתחות.",
                "Я часто забываю, куда кладу ключи.",
            ),
            _ex(
                "Ho dimenticato l'ombrello sull'autobus.",
                "I forgot my umbrella on the bus.",
                "Olvidé el paraguas en el autobús.",
                "שכחתי את המטרייה באוטובוס.",
                "Я забыл зонт в автобусе.",
            ),
            _ex(
                "Da giovane dimenticavo sempre i compleanni degli amici.",
                "As a young person I always used to forget my friends' birthdays.",
                "De joven siempre olvidaba los cumpleaños de mis amigos.",
                "כשהייתי צעיר תמיד הייתי שוכח את ימי ההולדת של החברים.",
                "В молодости я всегда забывал дни рождения друзей.",
            ),
            _ex(
                "Non dimenticherò mai questa esperienza.",
                "I will never forget this experience.",
                "Nunca olvidaré esta experiencia.",
                "לעולם לא אשכח את החוויה הזו.",
                "Я никогда не забуду этот опыт.",
            ),
            _ex(
                "Non dimenticare di spegnere la luce.",
                "Don't forget to turn off the light.",
                "No olvides apagar la luz.",
                "אל תשכח לכבות את האור.",
                "Не забудь выключить свет.",
            ),
        ],
    },
    {
        # No forced imperativo: a bare command ("Conosci!") doesn't read as
        # natural Italian for a stative cognition verb -- substituted an
        # interrogative presente instead, mirroring it_andare's own precedent
        # of a non-imperativo final example.
        "lemma": "conoscere",
        "cls": "ER",
        "stem": "conosc",
        "aux": "avere",
        "participio": "conosciuto",
        "translations": {
            "en": "to know (be acquainted with)",
            "es": "conocer",
            "ru": "знать (быть знакомым)",
            "he": "להכיר",
        },
        "examples": [
            _ex(
                "Conosco questa città molto bene.",
                "I know this city very well.",
                "Conozco esta ciudad muy bien.",
                "אני מכיר את העיר הזו טוב מאוד.",
                "Я очень хорошо знаю этот город.",
            ),
            _ex(
                "Ci siamo conosciuti all'università.",
                "We met each other at university.",
                "Nos conocimos en la universidad.",
                "הכרנו באוניברסיטה.",
                "Мы познакомились в университете.",
            ),
            _ex(
                "Da bambino conoscevo tutti i vicini di casa.",
                "As a child I knew all the neighbors.",
                "De niño conocía a todos los vecinos.",
                "כשהייתי ילד הכרתי את כל השכנים.",
                "В детстве я знал всех соседей.",
            ),
            _ex(
                "Conoscerai presto tutti i miei amici.",
                "You will soon meet all my friends.",
                "Pronto conocerás a todos mis amigos.",
                "בקרוב תכיר את כל החברים שלי.",
                "Ты скоро познакомишься со всеми моими друзьями.",
            ),
            _ex(
                "Conosci qualcuno che possa aiutarmi?",
                "Do you know someone who could help me?",
                "¿Conoces a alguien que pueda ayudarme?",
                "אתה מכיר מישהו שיכול לעזור לי?",
                "Ты знаешь кого-нибудь, кто мог бы мне помочь?",
            ),
        ],
    },
    {
        "lemma": "incontrare",
        "cls": "AR",
        "stem": "incontr",
        "aux": "avere",
        "participio": "incontrato",
        "translations": {"en": "to meet", "es": "encontrarse con/conocer", "ru": "встречать", "he": "לפגוש"},
        "examples": [
            _ex(
                "Incontro i miei colleghi ogni lunedì mattina.",
                "I meet my colleagues every Monday morning.",
                "Me reúno con mis colegas cada lunes por la mañana.",
                "אני נפגש עם עמיתיי כל יום שני בבוקר.",
                "Я встречаюсь с коллегами каждый понедельник утром.",
            ),
            _ex(
                "Abbiamo incontrato dei vecchi amici al mercato.",
                "We ran into some old friends at the market.",
                "Nos encontramos con unos viejos amigos en el mercado.",
                "פגשנו חברים ותיקים בשוק.",
                "Мы встретили старых друзей на рынке.",
            ),
            _ex(
                "Da giovane incontravo spesso i miei compagni di scuola al bar.",
                "As a young person I often used to meet my schoolmates at the café.",
                "De joven me encontraba a menudo con mis compañeros de escuela en el bar.",
                "כשהייתי צעיר הייתי פוגש לעתים קרובות את חברי לכיתה בבית קפה.",
                "В молодости я часто встречал одноклассников в кафе.",
            ),
            _ex(
                "Incontrerò il direttore domani pomeriggio.",
                "I will meet the director tomorrow afternoon.",
                "Me reuniré con el director mañana por la tarde.",
                "אפגוש את המנהל מחר אחר הצהריים.",
                "Завтра днём я встречусь с директором.",
            ),
            _ex(
                "Incontriamoci davanti al cinema alle otto.",
                "Let's meet in front of the cinema at eight.",
                "Encontrémonos frente al cine a las ocho.",
                "ניפגש מול הקולנוע בשמונה.",
                "Давай встретимся перед кинотеатром в восемь.",
            ),
        ],
    },
]


def _get_max_rank() -> int:
    from core.storage.firestore_db import get_db

    result = get_db().collection("verbs").where("language", "==", LANGUAGE).count().get()
    return result[0][0].value


def main() -> None:
    start_rank = _get_max_rank() + 1
    for offset, entry in enumerate(VERBS):
        rank = start_rank + offset
        lemma = entry["lemma"]
        forms = _build_forms(entry)
        examples = entry["examples"]
        doc = build_verb_document(
            language=LANGUAGE,
            verb_id=f"it_{lemma}",
            lemma=lemma,
            rank=rank,
            forms=forms,
            examples=examples,
            display_lemma=None,
            display_forms=None,
            morph=None,
            search_extract=[],
        )
        doc["lemma_translations"] = entry["translations"]
        doc["search_extract"] = build_search_extract_from_entry(language=LANGUAGE, entry=doc)
        upsert_verb(f"it_{lemma}", doc)
        print(f"[{rank}] wrote it_{lemma} ({len(examples)} examples)")


if __name__ == "__main__":
    main()
