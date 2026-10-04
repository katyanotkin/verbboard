from core.languages.fr.forms import normalize_subjonctif


def test_strips_que_and_qu_prefix_from_every_slot():
    payload = {
        "forms": {"subjonctif_present": {"je": "que je reçoive", "il": "qu'il reçoive", "ils": "Qu'ils reçoivent"}}
    }
    out = normalize_subjonctif(payload)["forms"]["subjonctif_present"]
    assert out == {"je": "je reçoive", "il": "il reçoive", "ils": "ils reçoivent"}


def test_already_clean_forms_and_missing_tense_are_untouched():
    clean = {"forms": {"subjonctif_present": {"je": "j'aie", "il": "il ait"}}}
    assert normalize_subjonctif(clean)["forms"]["subjonctif_present"] == {"je": "j'aie", "il": "il ait"}
    assert normalize_subjonctif({"forms": {"present": {"je": "reçois"}}}) == {"forms": {"present": {"je": "reçois"}}}
    assert normalize_subjonctif(None) is None
