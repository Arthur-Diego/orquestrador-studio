"""Store das abas de chat (ADR-036): persistência isolada em tmp via `studio_env`."""
import pytest


@pytest.fixture()
def sess(studio_env):
    from studio.chat import sessions
    return sessions


def test_create_get_list(sess):
    s = sess.create("Campanha do gelo", pid="gelo")
    assert s.status == "idle" and s.turns == 0 and s.pid == "gelo"
    assert sess.get(s.id).title == "Campanha do gelo"
    assert [x.id for x in sess.list_sessions()] == [s.id]


def test_patch_e_status_invalido(sess):
    s = sess.create()
    sess.patch(s.id, title="Renomeada", status="running")
    assert sess.get(s.id).title == "Renomeada" and sess.get(s.id).status == "running"
    with pytest.raises(ValueError):
        sess.patch(s.id, status="voando")


def test_archivar_some_da_lista_padrao(sess):
    s = sess.create("arquivar")
    sess.patch(s.id, status="archived")
    assert s.id not in [x.id for x in sess.list_sessions()]
    assert s.id in [x.id for x in sess.list_sessions(include_archived=True)]


def test_bump_turn(sess):
    s = sess.create()
    assert sess.bump_turn(s.id).turns == 1 and sess.bump_turn(s.id).turns == 2


def test_events_append_and_replay(sess):
    s = sess.create()
    assert sess.append_event(s.id, {"kind": "user", "text": "oi"}) == 0
    assert sess.append_event(s.id, {"kind": "assistant_text", "text": "olá"}) == 1
    todos = sess.read_events(s.id)
    assert [e["seq"] for e in todos] == [0, 1]
    assert todos[0]["text"] == "oi" and todos[0]["kind"] == "user"
    depois = sess.read_events(s.id, after=1)
    assert [e["seq"] for e in depois] == [1]


def test_get_inexistente(sess):
    with pytest.raises(KeyError):
        sess.get("nao-existe")
