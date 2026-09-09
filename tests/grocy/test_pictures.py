"""Les images : trois familles, une seule meurt.

Aucun test de ce fichier ne sort sur le réseau. Les URL Unsplash sont des
chaînes qu'on laisse tranquilles, jamais des adresses qu'on visite.
"""
import pytest

from custom_components.home_stock.grocy import pictures as gp


def test_the_three_families_on_the_real_data(grocy_reel):
    compte = {"inline": 0, "grocy": 0, "external": 0}
    for ligne in grocy_reel["recipes"]:
        for ref in gp.references(ligne["description"]):
            compte[ref.family] += 1
    assert compte == {"inline": 62, "grocy": 55, "external": 112}


def test_the_forty_six_distinct_unsplash_photos(grocy_reel):
    """112 emplacements, 46 images distinctes. Dette assumée et inscrite : le
    jour où elles tomberont, elles tomberont toutes ensemble."""
    vues = {ref.src for ligne in grocy_reel["recipes"]
            for ref in gp.references(ligne["description"]) if ref.family == "external"}
    assert len(vues) == 46


def test_a_grocy_url_decodes_to_its_file_name():
    """C'est du base64 du nom, sans clé d'API. Le décodage est fait par le
    code, jamais recopié à la main."""
    assert gp.nom_de_fichier(
        "https://grocy.allanic.me/api/files/recipepictures/cmVjZXR0ZS00MS0wLmpwZw=="
    ) == "recette-41-0.jpg"


def test_a_name_that_does_not_decode_is_an_anomaly_not_a_shrug():
    with pytest.raises(gp.PictureNameError):
        gp.nom_de_fichier("https://grocy.allanic.me/api/files/recipepictures/!!!!")


def test_the_fifty_five_grocy_names_all_decode(grocy_reel):
    noms = set()
    for ligne in grocy_reel["recipes"]:
        for ref in gp.references(ligne["description"]):
            if ref.family == "grocy":
                assert ref.filename.endswith(".jpg")
                noms.add(ref.filename)
    assert len(noms) == 55


def test_an_inline_name_is_deterministic():
    """Déterministe pour que le rejeu réécrive le MÊME fichier au lieu d'en
    accumuler un nouveau par passage : l'idempotence du §8.8, appliquée au
    système de fichiers."""
    assert gp.nom_inline(41, 0) == "recette-41-inline-0.jpg"
    assert gp.nom_inline(41, 0) == gp.nom_inline(41, 0)
    assert gp.nom_inline(41, 1) != gp.nom_inline(41, 0)


def test_a_media_id_is_never_a_www_path():
    """Le lot 5 a tranché : jamais sous www/, qui est servi SANS
    authentification à tout le réseau."""
    ident = gp.media_id("home_stock/recipes", "recette-41-0.jpg")
    assert ident == "media-source://media_source/local/home_stock/recipes/recette-41-0.jpg"
    assert "www" not in ident
    assert not ident.startswith("/local/")


def test_rewriting_replaces_grocy_and_inline_but_never_unsplash():
    html = (
        '<img src="https://grocy.allanic.me/api/files/recipepictures/'
        'cmVjZXR0ZS00MS0wLmpwZw==">'
        '<img src="data:image/jpeg;base64,AAAA">'
        '<img src="https://images.unsplash.com/photo-123">')
    sortie = gp.reecrire(html, {
        "https://grocy.allanic.me/api/files/recipepictures/cmVjZXR0ZS00MS0wLmpwZw==":
            "media-source://media_source/local/home_stock/recipes/recette-41-0.jpg",
        "data:image/jpeg;base64,AAAA":
            "media-source://media_source/local/home_stock/recipes/recette-1-inline-0.jpg",
    })
    assert "grocy.allanic.me" not in sortie
    assert "data:image" not in sortie
    assert "images.unsplash.com/photo-123" in sortie      # intact


def test_no_residual_grocy_url_after_rewriting_the_real_data(grocy_reel):
    """C9 en germe : 0 URL grocy.allanic.me résiduelle."""
    for ligne in grocy_reel["recipes"]:
        mapping = {r.src: "media-source://x"
                   for r in gp.references(ligne["description"])
                   if r.family in ("grocy", "inline")}
        assert "grocy.allanic.me" not in gp.reecrire(ligne["description"], mapping)


def test_an_inline_payload_is_written_as_a_real_file(tmp_path, grocy_reel):
    """La recette 69 garde ses data-URI intacts dans les fixtures, et c'est
    elle qui prouve qu'on écrit un VRAI JPEG. (La spec disait 41 ; la 41 n'en
    porte aucun — amendement A1 du § 22.)"""
    r69 = next(ligne for ligne in grocy_reel["recipes"] if ligne["id"] == 69)
    ref = next(r for r in gp.references(r69["description"]) if r.family == "inline")
    chemin = tmp_path / "recette-69-inline-0.jpg"
    octets = gp.ecrire_inline(ref.src, str(chemin))
    assert octets > 0
    assert chemin.stat().st_size == octets
    assert chemin.read_bytes()[:2] == b"\xff\xd8"      # un JPEG, pas du texte


def test_even_the_stubbed_payloads_decode_to_a_real_jpeg(tmp_path, grocy_reel):
    """Le stub des 60 autres est un JPEG 1×1 valide, pas un caractère de
    remplissage : un test qui écrirait du texte et vérifierait « ça pèse plus
    de zéro » ne prouverait rien du décodage."""
    recette = next(ligne for ligne in grocy_reel["recipes"]
                   if ligne["id"] != 69
                   and "data:image" in (ligne["description"] or ""))
    ref = next(r for r in gp.references(recette["description"])
               if r.family == "inline")
    chemin = tmp_path / "stub.jpg"
    gp.ecrire_inline(ref.src, str(chemin))
    octets = chemin.read_bytes()
    assert octets[:2] == b"\xff\xd8" and octets[-2:] == b"\xff\xd9"


def test_a_zero_byte_write_is_refused(tmp_path):
    """Un fichier de 0 octet passerait tous les contrôles de base et
    n'afficherait rien. C9 le rattraperait ; autant ne jamais l'écrire."""
    with pytest.raises(gp.PictureNameError):
        gp.ecrire_inline("data:image/jpeg;base64,", str(tmp_path / "vide.jpg"))


def test_reconciliation_reports_the_orphan_without_blocking():
    """0 référence sans fichier, 1 fichier sans référence (test.jpg). Le
    manquant bloque, l'orphelin se signale."""
    manquants, orphelins = gp.reconcilier(
        references={"a.jpg", "b.jpg"}, fichiers={"a.jpg", "b.jpg", "test.jpg"})
    assert manquants == set()
    assert orphelins == {"test.jpg"}


def test_a_missing_file_is_reported_as_missing():
    manquants, _ = gp.reconcilier(references={"a.jpg", "c.jpg"}, fichiers={"a.jpg"})
    assert manquants == {"c.jpg"}


def test_no_test_in_this_file_touches_the_network():
    import inspect
    source = inspect.getsource(gp)
    for interdit in ("urlopen", "requests.", "aiohttp", "httpx"):
        assert interdit not in source
