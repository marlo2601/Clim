"""Test de bout en bout du blueprint de pilotage, dans un vrai Home Assistant."""
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as ha_yaml
import homeassistant.util.dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

REPO = Path(__file__).resolve().parent.parent / "homeassistant"
TZ = ZoneInfo("Europe/Paris")
PIECES = ["salon", "chambre_1", "chambre_2", "bureau"]


async def avancer(hass, freezer, quand):
    freezer.move_to(quand)
    async_fire_time_changed(hass, quand)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, quand + timedelta(seconds=1))
    await hass.async_block_till_done()


@pytest.fixture
async def setup(hass, tmp_path, freezer):
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to(datetime(2026, 11, 9, 5, 0, tzinfo=TZ))  # lundi 5h
    hass.config.config_dir = str(tmp_path)
    shutil.copytree(REPO / "blueprints", tmp_path / "blueprints")

    pkg = ha_yaml.load_yaml(str(REPO / "packages/clim.yaml"))
    # Capteur de présence dans le salon uniquement (les autres pièces : aucun).
    autos = pkg["automation clim"]
    autos[0]["use_blueprint"]["input"] = dict(autos[0]["use_blueprint"]["input"])
    autos[0]["use_blueprint"]["input"]["capteurs_presence"] = ["binary_sensor.presence_salon"]

    # Fausses clims : l'état suit les ordres reçus.
    appels = []
    for p in PIECES:
        hass.states.async_set(f"climate.{p}", "off", {"temperature": 20})

    async def set_temp(call):
        appels.append(("set", call.data))
        for e in call.data["entity_id"]:
            hass.states.async_set(e, call.data["hvac_mode"], {"temperature": call.data["temperature"]})

    async def turn_off(call):
        appels.append(("off", call.data))
        for e in call.data["entity_id"]:
            hass.states.async_set(e, "off", hass.states.get(e).attributes)

    hass.services.async_register("climate", "set_temperature", set_temp)
    hass.services.async_register("climate", "turn_off", turn_off)

    hass.states.async_set("binary_sensor.presence_salon", "on")
    hass.states.async_set("person.moi", "home")
    hass.states.async_set("zone.home", "1")

    lundi = [
        {"from": "06:30:00", "to": "08:30:00", "data": {"temp_chaud": 21, "temp_froid": 25}},
        {"from": "22:00:00", "to": "24:00:00", "data": {"temp_chaud": 19, "ignorer_presence": True}},
    ]
    assert await async_setup_component(hass, "schedule", {"schedule": {
        f"clim_{p}": {"name": f"Clim {p}", "monday": lundi} for p in PIECES}})
    for dom in ("input_select", "input_number", "input_boolean"):
        assert await async_setup_component(hass, dom, {dom: pkg[dom]})
    await hass.async_block_till_done()
    for nom, val in [("confort_chaud", 20), ("confort_froid", 26), ("absent_chaud", 17), ("absent_froid", 28)]:
        await hass.services.async_call("input_number", "set_value",
            {"entity_id": f"input_number.clim_{nom}", "value": val}, blocking=True)
    assert await async_setup_component(hass, "automation", {"automation": autos})
    await hass.async_block_till_done()
    return appels


def etat(hass, p="salon"):
    s = hass.states.get(f"climate.{p}")
    return s.state, s.attributes.get("temperature")


async def test_scenario(hass, setup, freezer):
    # Les 4 automatisations existent et sont valides
    autos = hass.states.async_all("automation")
    assert len(autos) == 4, autos
    assert all(a.state == "on" for a in autos), autos

    hass.states.async_set("climate.salon", "heat", {"temperature": 23})
    # Auto activé, hors créneau -> arrêt
    for p in PIECES:
        await hass.services.async_call("input_boolean", "turn_on",
            {"entity_id": f"input_boolean.clim_auto_{p}"}, blocking=True)
    await hass.async_block_till_done()
    assert etat(hass) == ("off", 23)

    # 6h30 : créneau 21°C
    await avancer(hass, freezer, datetime(2026, 11, 9, 6, 30, 5, tzinfo=TZ))
    assert etat(hass) == ("heat", 21)
    assert etat(hass, "bureau") == ("heat", 21)

    # Pièce vide 20 min -> absent 17°C (seulement le salon a un capteur)
    hass.states.async_set("binary_sensor.presence_salon", "off")
    await hass.async_block_till_done()
    await avancer(hass, freezer, datetime(2026, 11, 9, 6, 40, tzinfo=TZ))
    assert etat(hass) == ("heat", 21)
    await avancer(hass, freezer, datetime(2026, 11, 9, 6, 51, tzinfo=TZ))
    assert etat(hass) == ("heat", 17)
    assert etat(hass, "bureau") == ("heat", 21)

    # Retour dans la pièce
    hass.states.async_set("binary_sensor.presence_salon", "on")
    await hass.async_block_till_done()
    assert etat(hass) == ("heat", 21)

    # Plus personne à la maison -> tout en absent
    hass.states.async_set("zone.home", "0")
    await hass.async_block_till_done()
    assert etat(hass) == ("heat", 17)
    assert etat(hass, "bureau") == ("heat", 17)
    hass.states.async_set("zone.home", "1")
    await hass.async_block_till_done()
    assert etat(hass, "bureau") == ("heat", 21)

    # Saison clim -> temp_froid du créneau
    await hass.services.async_call("input_select", "select_option",
        {"entity_id": "input_select.clim_saison", "option": "Climatisation"}, blocking=True)
    await hass.async_block_till_done()
    assert etat(hass) == ("cool", 25)
    await hass.services.async_call("input_select", "select_option",
        {"entity_id": "input_select.clim_saison", "option": "Chauffage"}, blocking=True)
    await hass.async_block_till_done()

    # Fin du créneau -> arrêt
    await avancer(hass, freezer, datetime(2026, 11, 9, 8, 30, 5, tzinfo=TZ))
    assert etat(hass)[0] == "off"

    # Pause auto : rien ne bouge
    await hass.services.async_call("input_boolean", "turn_off",
        {"entity_id": "input_boolean.clim_auto_bureau"}, blocking=True)

    # 22h : créneau nuit 19°C qui ignore la présence, même si maison vide
    hass.states.async_set("zone.home", "0")
    await hass.async_block_till_done()
    await avancer(hass, freezer, datetime(2026, 11, 9, 22, 0, 5, tzinfo=TZ))
    assert etat(hass) == ("heat", 19)
    assert etat(hass, "chambre_1") == ("heat", 19)
    assert etat(hass, "bureau")[0] == "off"  # pause respectée

    # Saison Arrêt -> tout s'éteint
    await hass.services.async_call("input_select", "select_option",
        {"entity_id": "input_select.clim_saison", "option": "Arrêt"}, blocking=True)
    await hass.async_block_till_done()
    assert etat(hass)[0] == "off"


async def test_pas_d_ordre_inutile(hass, setup, freezer):
    appels = setup
    for p in PIECES:
        await hass.services.async_call("input_boolean", "turn_on",
            {"entity_id": f"input_boolean.clim_auto_{p}"}, blocking=True)
    await avancer(hass, freezer, datetime(2026, 11, 9, 6, 30, 5, tzinfo=TZ))
    n = len(appels)
    # Un changement sans effet (zone.home 1 -> 2) ne renvoie aucun ordre
    hass.states.async_set("zone.home", "2")
    await hass.async_block_till_done()
    assert len(appels) == n
