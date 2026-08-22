import pytest
from app.broker_config import ExecutionMode,load_broker_config,redact


def test_default_is_paper(monkeypatch):
    monkeypatch.delenv('BROKER_MODE',raising=False); monkeypatch.delenv('BROKER_API_KEY',raising=False); monkeypatch.delenv('BROKER_API_SECRET',raising=False)
    cfg=load_broker_config(); assert cfg.mode==ExecutionMode.PAPER; assert cfg.credentials is None


def test_live_requires_credentials(monkeypatch):
    monkeypatch.setenv('BROKER_MODE','LIVE'); monkeypatch.delenv('BROKER_API_KEY',raising=False); monkeypatch.delenv('BROKER_API_SECRET',raising=False)
    with pytest.raises(RuntimeError): load_broker_config()


def test_live_credentials_are_loaded(monkeypatch):
    monkeypatch.setenv('BROKER_MODE','LIVE'); monkeypatch.setenv('BROKER_API_KEY','key123'); monkeypatch.setenv('BROKER_API_SECRET','secret456')
    cfg=load_broker_config(); assert cfg.credentials.api_key=='key123'; assert cfg.credentials.api_secret=='secret456'


def test_redaction():
    assert redact('abcdef')=='ab***ef'; assert redact('x')=='***'
