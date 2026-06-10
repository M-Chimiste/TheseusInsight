"""Characterize settings: default orchestration config + secret encryption."""


def test_orchestration_defaults(client, empty_db, db, golden):
    # On a DB with no stored orchestration config, the endpoint serves
    # code-level defaults. Freeze them: this shape feeds every pipeline.
    db.execute("DELETE FROM settings WHERE key = 'orchestration'")
    resp = client.get("/api/settings/orchestration")
    assert resp.status_code == 200
    golden("orchestration_defaults", resp.json())


def test_secret_setting_roundtrip_and_format(empty_db, golden):
    """Pin the XOR/base64 secret scheme so stored credentials survive refactors.

    APP_SECRET_KEY is fixed to 'test_secret' in conftest, so the ciphertext
    is deterministic.
    """
    from theseus_insight.data_access.settings import SettingsRepository

    SettingsRepository.set_secret_setting("characterization_secret", "hunter2-secret")
    assert SettingsRepository.get_secret_setting("characterization_secret") == "hunter2-secret"

    ciphertext = SettingsRepository.get("characterization_secret")
    assert ciphertext != "hunter2-secret"
    golden("secret_setting_ciphertext", ciphertext)
