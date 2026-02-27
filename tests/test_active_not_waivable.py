# tests/test_active_not_waivable.py

from govy.matching.models import ItemRequirement, WaiverConfig, GapCode
from govy.matching.matcher import match_item_to_bula


def test_active_missing_is_never_waived():
    req = ItemRequirement(
        raw="RITUXIMABE 10 MG/ML SOLUCAO INJETAVEL FRASCO-AMPOLA 50 ML",
        principle="RITUXIMABE",
        conc_num=10.0, conc_unit="MG", conc_den_unit="ML",
        form="SOLUCAO INJETAVEL",
        pkg="FRASCO-AMPOLA",
        vol=50.0, vol_unit="ML",
    )

    # Bula NÃO contém o princípio exigido, mas contém todo o resto
    bula_text = "MEDICAMENTO: OUTRO; 10 MG/ML; SOLUCAO INJETAVEL; FRASCO-AMPOLA 50 ML"

    # Mesmo que o payload venha com ignore_principle=True, isso NÃO pode suprimir ACTIVE_MISSING
    waivers = WaiverConfig(
        ignore_principle=True,
        ignore_concentration=False,
        ignore_form=False,
        ignore_pkg=False,
        ignore_volume=False,
    )

    r = match_item_to_bula("38", req, bula_text, waivers=waivers)

    assert r.status == "UNMATCH"
    assert any(g.code == GapCode.ACTIVE_MISSING for g in r.gaps)
    assert all(g.code != GapCode.ACTIVE_MISSING for g in r.waived_gaps)
