# Clim – pilotage des 4 Daikin FTXS25K depuis le téléphone

Plannings horaires, une température par créneau, mode chauffage ou clim, baisse
automatique quand la pièce est vide ou quand plus personne n'est à la maison. Le
tout se règle depuis l'app **Home Assistant** sur le téléphone.

```
 Téléphone (app Home Assistant)
          │  Wi‑Fi / Internet
          ▼
 Home Assistant Green  ──Wi‑Fi (local)──►  4 × module Faikin  ──prise S21──►  4 × Daikin FTXS25K
   (plannings, présence,                      (un par clim)
    automatisations de ce dépôt)
```

## 1. Matériel à acheter

| Quoi | Combien | Prix indicatif | Rôle |
|---|---|---|---|
| **Home Assistant Green** | 1 | ~130 € | Petit boîtier allumé en permanence, branché sur la box en Ethernet. Rien à installer, il est prêt à l'emploi. |
| **Module Faikin** (version S21, open source, conçu par RevK) | 4 | ~30‑40 € pièce | Se branche dans chaque clim et la relie au Wi‑Fi, en local, sans cloud Daikin. |
| *(facultatif)* Capteurs de présence **mmWave** Zigbee + clé Zigbee (ex. Home Assistant Connect ZBT‑1) | 1 par pièce + 1 clé | ~20‑40 € pièce, ~40 € la clé | Présence pièce par pièce. Prendre de la **mmWave** et pas un simple détecteur de mouvement (PIR), sinon une personne immobile, sur le canapé ou au lit, est vue comme partie. |

Budget de départ, **sans** capteurs : environ 250‑290 €.

> **Pourquoi pas le capteur « Intelligent Eye » des clims ?** Il fait ses économies
> en interne (environ −2 °C au bout de 20 min sans personne), mais l'information
> « présent / absent » ne sort pas de la clim. Donc :
> - **gratuit** : la présence des téléphones. Quand plus personne n'est à la maison,
>   tout passe en mode absent ;
> - **pièce par pièce** : les capteurs mmWave facultatifs ci-dessus.
>
> Tu peux aussi laisser l'Intelligent Eye actif sur la télécommande : il continue
> de faire ses petites économies de son côté.

## 2. Installation

### 2.1 Home Assistant Green
1. Branche-le sur la box (câble Ethernet) et sur le secteur.
2. Sur le téléphone, installe l'app **Home Assistant** et suis l'assistant :
   création du compte, nom de la maison, fuseau horaire.
3. Autorise la **localisation** dans l'app. C'est elle qui indique « à la maison »
   ou « absent ». Fais de même sur le téléphone des autres personnes du foyer.

### 2.2 Modules Faikin (un par clim)
1. **Coupe le disjoncteur des clims.**
2. Ouvre le capot avant de l'unité intérieure, puis le couvercle du boîtier
   électronique, et branche le Faikin sur le connecteur **S21**. La notice Faikin
   montre l'emplacement. Si tu n'es pas à l'aise, un installateur clim le fait en
   quelques minutes.
3. Remets le courant. Le Faikin crée un réseau Wi‑Fi « Faikin‑… » : connecte-toi
   dessus avec le téléphone et renseigne ton Wi‑Fi.
4. Dans Home Assistant : **Paramètres > Modules complémentaires > Boutique** :
   installe **Mosquitto broker** et démarre-le. Ensuite, dans **Paramètres >
   Appareils et services**, ajoute l'intégration **MQTT** proposée.
5. Dans la page web de chaque Faikin, renseigne le serveur MQTT (l'adresse du
   Home Assistant Green, avec un utilisateur Home Assistant) et active la
   découverte Home Assistant. Les 4 clims apparaissent alors dans Home Assistant.
6. **Renomme les entités** pour qu'elles s'appellent exactement
   `climate.salon`, `climate.chambre_1`, `climate.chambre_2` et `climate.bureau`.
   Si tes pièces portent d'autres noms, adapte plutôt
   `homeassistant/packages/clim.yaml`.

### 2.3 Copier la configuration de ce dépôt
1. Installe le module complémentaire **Studio Code Server** ou **File editor**.
2. Copie dans le dossier `/config` de Home Assistant :
   - `homeassistant/blueprints/automation/clim/pilotage_clim.yaml` vers
     `/config/blueprints/automation/clim/pilotage_clim.yaml`
   - `homeassistant/packages/clim.yaml` vers `/config/packages/clim.yaml`
3. Dans `/config/configuration.yaml`, ajoute :
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
4. **Paramètres > Système > Redémarrer**.

### 2.4 Créer les 4 plannings (depuis le téléphone)
**Paramètres > Appareils et services > Entrées > Créer une entrée > Planning**,
une fois par pièce, avec ces noms exacts :
`Clim salon`, `Clim chambre 1`, `Clim chambre 2`, `Clim bureau`.
Ils deviennent `schedule.clim_salon`, etc.

Dessine les créneaux pendant lesquels la clim doit tourner. **Hors créneau, la
clim est éteinte.** Pour donner une température précise à un créneau, ouvre-le et
ajoute dans ses données avancées :

```yaml
temp_chaud: 21      # consigne en mode chauffage
temp_froid: 25      # consigne en mode clim
ignorer_presence: true   # facultatif : ex. la nuit, ne jamais baisser
```

Sans données, le créneau utilise les températures de confort par défaut.

Exemple pour une chambre : 6h30‑8h00 à 20 °C, 21h00‑24h00 à 19 °C avec
`ignorer_presence: true`.

### 2.5 Tableau de bord du téléphone
**Paramètres > Tableaux de bord > Ajouter un tableau de bord** (« Clim »). Ouvre-le,
puis **⋮ > Modifier > ⋮ > Éditeur de configuration brute**, et colle le contenu de
`homeassistant/dashboards/clim.yaml`.

### 2.6 Premiers réglages
Dans le tableau de bord :
- choisis la **saison** : Chauffage, Climatisation ou Arrêt ;
- règle les 4 températures : confort chauffage / clim, et absent chauffage / clim.
  Au premier démarrage, elles valent le minimum de leur plage ;
- active **Pilotage auto** pour chaque pièce. Au premier démarrage, il est désactivé.

## 3. Comment ça marche

Pour chaque pièce, à chaque changement (début ou fin de créneau, présence, saison,
réglage…), l'automatisation calcule ce que la clim doit faire :

| Situation | Résultat |
|---|---|
| Saison « Arrêt » ou hors créneau | Clim éteinte |
| Dans un créneau, quelqu'un est là | Mode de la saison + température du créneau |
| Pièce vide depuis 20 min (capteur), **ou** plus personne à la maison (téléphones) | Température « absent », ou arrêt au choix |
| Créneau avec `ignorer_presence: true` | Température du créneau, même si absent |
| « Pilotage auto » coupé | Rien n'est touché : tu fais ce que tu veux à la télécommande |

- Un ordre n'est envoyé que si quelque chose change. Pas de bip inutile.
- Un réglage fait à la télécommande reste en place jusqu'au prochain changement
  (créneau, présence…). Pour garder la main plus longtemps, coupe « Pilotage auto »
  de la pièce.
- Si un capteur de présence est hors ligne, la pièce est considérée comme occupée :
  on privilégie le confort.

### Ajouter un capteur de présence à une pièce
Dans `packages/clim.yaml`, sous l'automatisation de la pièce, ajoute :
```yaml
        capteurs_presence:
          - binary_sensor.presence_salon
        delai_absence: 20          # minutes
        action_absence: eco        # ou "arret"
```
Tu peux aussi créer l'automatisation depuis l'interface : **Paramètres >
Automatisations > Blueprints > « Pilotage clim Daikin »**. Tous les champs y sont
expliqués.

## 4. Tests (pour les développeurs)
Les tests lancent un vrai Home Assistant avec de fausses clims et simulent une
journée : créneaux, absence, retour, saison, nuit, pause.
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-test.txt
pytest
```
