"""Test-Fixtures: Kopie der String-Tabellen mit gezielt eingebauten Defekten.

Der echte Korpus ist inzwischen bereinigt (K1/K2/K3 behoben) — damit die Regeln
weiter etwas zu finden haben, baut defect_copy() die typischen Fälle über den
Writer in eine KOPIE ein:
  K1  Otho.Signal mit veralteter englischer ID
  K2  Wasserritual-Antwort in Höflichkeitsform („Euer Durst …“)
  K3  AIWiring-Meldung mit konjde ohne Subjekt-Namen
  K5  Agyra-Begrüßung mit englischen ifplayerplural-Argumenten
"""
import os
import shutil
import tempfile

from curator import config, writer
from curator.store import Store

FILES = ("Strings.de.xml", "Strings.Conversations.de.xml")
K1_CONTEXT = "Conversation Otho.Signal.Text"
K2_CONTEXT = "Conversation BaseConversation.WaterRitualChoice.Text"
K3_CONTEXT = "AIWiring - Ignore Conversation Message"
K5_CONTEXT = "Conversation Agyra.Start.Text"


def defect_copy():
    """-> (tempdir, Store). Aufrufer räumt tempdir auf (shutil.rmtree)."""
    d = tempfile.mkdtemp()
    for fn in FILES:
        shutil.copy(os.path.join(config.LANG_DE, fn), os.path.join(d, fn))
    st = Store(d)
    st.refresh()
    by_ctx = {}
    for u in st.all_units():
        by_ctx.setdefault(u.context, u)
    # K2: Höflichkeitsform
    u = by_ctx[K2_CONTEXT]
    writer.save(st, u.uid, u.display_value(), "Euer Durst ist meiner, mein Wasser ist eures.")
    # K3: konjde ohne Subjekt
    u = by_ctx[K3_CONTEXT]
    writer.save(st, u.uid, u.display_value(), "=subject.Konjde:ignorieren= =object.the.name=.")
    # K5: Weichen-Token mit englischen Argumenten
    u = by_ctx[K5_CONTEXT]
    writer.save(st, u.uid, u.display_value(),
                "=ifplayerplural:Ye have:Thou hast= die Welt verändert.")
    # K1: aktuellen Eintrag durch einen mit alter ID ersetzen
    u = by_ctx[K1_CONTEXT]
    val = u.display_value()
    writer.delete_string_entry(st, u.uid, val)
    writer.create_string_entry(st, u.file, K1_CONTEXT, u.english.replace("=V0tinkeraddendum=",
                                                                         "(alte Fassung)"), val)
    st.refresh()
    return d, st
