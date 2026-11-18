from . import sadtalker_runner, tts_piper, wav2lip_runner

# Motor de avatar seleccionable (config AVATAR_ENGINE / settings.avatar_engine).
# Default: wav2lip — mucho más rápido en CPU que SadTalker (solo sincroniza
# los labios, no mueve la cabeza). Ambos runners exponen la misma firma
# pública (is_installed, generate_talking_head, ENGINE_NAME, SETUP_DOC), así
# que quien los usa no necesita saber cuál es.
_ENGINES = {"sadtalker": sadtalker_runner, "wav2lip": wav2lip_runner}


def avatar_engine(name: str | None):
    return _ENGINES.get((name or "").lower(), wav2lip_runner)


__all__ = ["sadtalker_runner", "wav2lip_runner", "tts_piper", "avatar_engine"]
