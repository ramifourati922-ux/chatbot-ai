# Exposer les webhooks WhatsApp / Messenger avec ngrok

Ce guide explique comment exposer ton serveur local (`localhost:8000`)
sur une URL HTTPS publique temporaire, nécessaire pour configurer les
webhooks WhatsApp Cloud API et Messenger dans l'interface Meta
Developer (Meta exige HTTPS + une URL publique, `localhost` ne
fonctionne pas).

À faire une fois que tu as un compte Meta Developer + une app créée
(voir prérequis en bas de page).

## 1. Installer ngrok (Windows)

Option A — via un gestionnaire de paquets, si tu en as un installé :
```powershell
choco install ngrok
# ou
winget install ngrok.ngrok
```

Option B — manuel :
1. Va sur https://ngrok.com/download
2. Télécharge le zip Windows, extrait `ngrok.exe` quelque part (ex: `C:\tools\ngrok\`)
3. Ajoute ce dossier à ton PATH, ou lance `ngrok.exe` depuis ce dossier directement

## 2. Créer un compte ngrok + connecter ton authtoken

Un compte gratuit suffit amplement pour du développement/tests.

1. Crée un compte sur https://dashboard.ngrok.com/signup
2. Récupère ton authtoken ici : https://dashboard.ngrok.com/get-started/your-authtoken
3. Connecte-le en local (une seule fois) :
```powershell
ngrok config add-authtoken TON_AUTHTOKEN_ICI
```

## 3. Lancer ton serveur local, puis ngrok

Dans un premier terminal, lance l'app (comme d'habitude) :
```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dans un second terminal, expose le port 8000 :
```powershell
ngrok http 8000
```

Tu obtiens un affichage du type :
```
Forwarding    https://a1b2-c3d4-e5f6.ngrok-free.app -> http://localhost:8000
```

C'est **cette URL HTTPS** (`https://a1b2-c3d4-e5f6.ngrok-free.app`)
que tu vas donner à Meta. Elle change à **chaque redémarrage** de
ngrok (sauf domaine statique payant) — il faudra reconfigurer le
webhook côté Meta si tu relances ngrok un autre jour.

Astuce : ngrok fournit une interface web locale sur
http://127.0.0.1:4040 qui montre le détail de chaque requête reçue
(headers, body) — très utile pour déboguer le format exact envoyé par
Meta si quelque chose ne matche pas.

## 4. Avant de configurer le webhook — remplacer les valeurs de TEST

Le code (Tâches 1 et 2) tourne actuellement avec des valeurs de test
dans `.env` :
```
WHATSAPP_VERIFY_TOKEN=test-verify-token
WHATSAPP_APP_SECRET=test-app-secret-12345
MESSENGER_VERIFY_TOKEN=test-verify-token-messenger
MESSENGER_APP_SECRET=test-app-secret-messenger-67890
```

Avant de connecter un vrai webhook Meta :
- `WHATSAPP_VERIFY_TOKEN` / `MESSENGER_VERIFY_TOKEN` : remplace par
  n'importe quelle chaîne secrète de ton choix (ce n'est PAS fourni
  par Meta, c'est toi qui l'inventes et la ressaisis dans leur
  interface).
- `WHATSAPP_APP_SECRET` / `MESSENGER_APP_SECRET` : remplace par la
  vraie valeur fournie par Meta (voir étape 5 ci-dessous — sinon la
  vérification de signature échouera sur tous les vrais messages
  Meta et le webhook rejettera tout en 403).

Redémarre uvicorn après avoir modifié `.env`.

## 5. Prérequis côté Meta (à faire une seule fois)

1. Crée un compte développeur sur https://developers.facebook.com/
2. Crée une "App" (type "Business")
3. Récupère `WHATSAPP_APP_SECRET`/`MESSENGER_APP_SECRET` : dans
   l'app > **Paramètres** > **Général** > "Clé secrète de l'app"
   (bouton "Afficher", demande ton mot de passe Facebook)

## 6. Configurer le webhook WhatsApp

1. Dans ton app Meta : ajoute le produit **WhatsApp**
2. Section **Configuration** > **Webhook** > "Modifier"
3. **URL de rappel (Callback URL)** :
   `https://<ton-url-ngrok>.ngrok-free.app/webhook/whatsapp`
4. **Token de vérification** : la valeur que tu as mise dans
   `WHATSAPP_VERIFY_TOKEN` (`.env`)
5. Clique **"Vérifier et enregistrer"** — Meta appelle
   `GET /webhook/whatsapp` avec `hub.challenge`, ton serveur doit
   répondre 200 avec le challenge en texte brut (déjà implémenté,
   Tâche 1). Si ça échoue : vérifie qu'uvicorn tourne, que ngrok
   tourne toujours, et que le token correspond exactement.
6. Une fois vérifié, **abonne-toi au champ `messages`** (case à
   cocher "messages" dans la liste des webhook fields) — sinon Meta
   ne t'enverra jamais les messages entrants, seulement les autres
   événements.
7. Récupère `WHATSAPP_PHONE_NUMBER_ID` et `WHATSAPP_ACCESS_TOKEN` :
   section **Premiers pas / Getting started** de l'app WhatsApp — un
   numéro de test Meta est fourni gratuitement pour le développement
   (limité à quelques destinataires vérifiés). Renseigne ces 2
   valeurs dans `.env`.

## 7. Configurer le webhook Messenger

1. Dans ton app Meta : ajoute le produit **Messenger**
2. Il te faut une **Page Facebook** (crées-en une si besoin, gratuit)
3. Section **Messenger** > **Paramètres** > **Webhooks** > "Ajouter une URL de rappel"
4. **URL de rappel** : `https://<ton-url-ngrok>.ngrok-free.app/webhook/messenger`
5. **Token de vérification** : la valeur de `MESSENGER_VERIFY_TOKEN`
6. **Vérifier et enregistrer**, puis abonne-toi aux champs
   `messages` (et `messaging_postbacks` si tu ajoutes des boutons
   plus tard)
7. Génère un **Page Access Token** : section Messenger > sélectionne
   ta Page > "Générer un token" → renseigne-le dans
   `MESSENGER_PAGE_ACCESS_TOKEN` (`.env`)

## 8. Tester avec un vrai message

- **WhatsApp** : depuis un téléphone dont le numéro est ajouté à la
  liste des destinataires de test (section Getting Started), envoie
  un message au numéro de test WhatsApp affiché dans l'interface Meta.
- **Messenger** : ouvre ta Page Facebook et envoie-lui un message via
  Messenger (toi-même en tant qu'admin de la Page peux tester
  directement).

Surveille les logs uvicorn — tu dois voir les mêmes traces que dans
les tests simulés des Tâches 1/2 (`Session créée`, `intent=...`,
etc.), et l'inspecteur ngrok (http://127.0.0.1:4040) pour voir la
requête brute si quelque chose ne correspond pas au format attendu.

## Points de vigilance

- **URL ngrok éphémère** : à chaque redémarrage de `ngrok http 8000`
  sans domaine statique payant, l'URL change → il faut retourner
  configurer le Callback URL dans Meta à chaque fois.
- **Mode développement de l'app Meta** : par défaut, une app Meta en
  mode "Développement" ne peut envoyer/recevoir des messages
  qu'avec des comptes explicitement ajoutés comme testeurs/admins —
  suffisant pour cette phase, mais il faudra passer l'app en mode
  "Live" + validation Meta pour un vrai lancement public.
- **Redémarrer uvicorn** après chaque modification de `.env` (les
  settings sont chargés une fois au démarrage, via `lru_cache`).
- **Ne jamais commit `.env`** avec de vrais tokens/secrets une fois
  renseignés (déjà dans `.gitignore`).
